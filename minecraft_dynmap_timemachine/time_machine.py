import io
import logging
import os
import time
from threading import Thread

from PIL import Image
import progressbar
from progressbar import ETA, Bar, Percentage, ProgressBar

from . import projection, simple_downloader


class TimeMachine(object):

    def __init__(self, dm_map, max_threads, cache_path, clean_cache):
        self._dm_map = dm_map
        # self.dynmap = dynmap.DynMap(url)
        self.download_threads = []
        self.max_threads = max_threads
        self.cache_path = cache_path
        self._clean_cache = clean_cache
        if not os.path.exists(self.cache_path):
            os.makedirs(self.cache_path)

    def _download_tile_thread(self, url):
        filename = url.split('/')[-1]
        if os.path.exists('{}/{}'.format(self.cache_path, filename)) and os.path.getsize('{}/{}'.format(self.cache_path, filename)) > 0:
            logging.debug('Tile already downloaded: %s', filename)
            return
        try:
            img_data = simple_downloader.download(url, True)
            # save image data to cache folder
            stream = io.BytesIO(img_data)
            img = Image.open(stream)
            if filename.endswith('.jpg'):
                img = img.convert('RGB')
            with open(f"{self.cache_path}/{filename}", 'wb') as f:
                img.save(f)
        except Exception as e:
            logging.info('Unable to download "%s": %s', url, str(e))
            return

    def _clear_threads(self):
        while len(self.download_threads) > 0:
            time.sleep(0.1)
            # clear finished threads
            for th in self.download_threads:
                if not th.is_alive():
                    self.download_threads.remove(th)

    def clean_cache(self):
        if self._clean_cache:
            for file in os.listdir(self.cache_path):
                file_path = os.path.join(self.cache_path, file)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logging.error(e)

    def capture_single(self, map, t_loc, size):
        from_tile, to_tile = t_loc.make_range(size[0], size[1])
        zoomed_scale = projection.zoomed_scale(t_loc.zoom)

        width, height = (abs(to_tile.x - from_tile.x) * 128 / zoomed_scale, abs(to_tile.y - from_tile.y) * 128 / zoomed_scale)
        logging.info('Final size in px: [%d, %d]', width, height)
        dest_img = Image.new('RGB', (int(width), int(height)))

        logging.info('Downloading tiles...')
        # logging.info('tile image path: %s', image_url)

        widgets = ['Download Tiles: ', Percentage(), ' ', Bar(marker='\u2588', fill='\u2591'), ' ', ETA()]
        pbar = ProgressBar(widgets=widgets, maxval=(((to_tile.x-from_tile.x)/zoomed_scale) *
                                                    ((to_tile.y-from_tile.y)/zoomed_scale)), term_width=96)

        processed = 0
        for x in range(from_tile.x, to_tile.x, zoomed_scale):
            for y in range(from_tile.y, to_tile.y, zoomed_scale):
                if self.max_threads < len(self.download_threads):
                    # wait for threads to finish
                    self._clear_threads()
                img_rel_path = map.image_url(projection.TileLocation(x, y, t_loc.zoom))
                img_url = self._dm_map.url + img_rel_path
                processed += 1
                pbar.update(processed)
                # logging.info('Download tile %d/%d [%d, %d]', processed, total_tiles, x, y)
                th = Thread(target=self._download_tile_thread, args=(img_url,))
                th.start()
                self.download_threads.append(th)

        # wait for threads to finish
        self._clear_threads()
        pbar.finish()

        # combine tiles into one image
        logging.info('Combining tiles...')

        widgets = ['Combine Tiles:  ', Percentage(), ' ', Bar(marker='\u2588', fill='\u2591'), ' ', ETA()]
        pbar = ProgressBar(widgets=widgets, maxval=(((to_tile.x-from_tile.x)/zoomed_scale) *
                                                    ((to_tile.y-from_tile.y)/zoomed_scale)), term_width=96)

        processed = 0
        for x in range(from_tile.x, to_tile.x, zoomed_scale):
            for y in range(from_tile.y, to_tile.y, zoomed_scale):
                img_rel_path = map.image_url(projection.TileLocation(x, y, t_loc.zoom))
                filename = img_rel_path.split('/')[-1]
                img_path = f"{self.cache_path}/{filename}"
                processed += 1
                pbar.update(processed)
                # logging.info('Combine tile %d/%d [%d, %d]', processed, total_tiles, x, y)
                try:
                    im = Image.open(img_path)
                except Exception as e:
                    logging.info('Unable to open "%s": %s', img_path, str(e))
                    continue

                box = (int(abs(x - from_tile.x) * 128 / zoomed_scale), int((abs(to_tile.y - y) - zoomed_scale) * 128 / zoomed_scale))
                logging.debug('Place to [%d, %d]', box[0], box[1])
                dest_img.paste(im, box)
        pbar.finish()

        return dest_img


    def compare_images(self, image1, image2):
        file1data = list(image1.getdata())
        file2data = list(image2.getdata())

        diff = 0
        for i in range(len(file1data)):
            if file1data[i] != file2data[i]:
                diff += 1

        return float(diff) / len(file1data)
