#!/usr/bin/env python

import logging
import argparse
import glob
import sys
import time
import os
from PIL import Image

import minecraft_dynmap_timemachine.dynmap as dynmap
import minecraft_dynmap_timemachine.time_machine as time_machine
import minecraft_dynmap_timemachine.projection as projection


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('base_url', help='Dynamp server URL')
    parser.add_argument('world', nargs='?', help='world name, use --list-worlds to list available worlds')
    parser.add_argument('map', nargs='?', help='map name, use --list-maps to list available maps')
    parser.add_argument('center', nargs='?', help='minecraft cooridnates, use format: [x,y,z]')
    parser.add_argument('boundary_size', nargs='?', help='size in tiles, use format: [w,h]')
    parser.add_argument('zoom', nargs='?', default='0', help='zoom level, 0 = maximum zoom in')
    parser.add_argument('dest', nargs='?', help='output file name or directory, without extension(format)')
    parser.add_argument('-f', '--image-format', default='png', help='output file format, default: png')
    parser.add_argument('-th', '--threads', default='16', help='number of threads to use, default: 16')
    parser.add_argument('-cd', '--cache-dir', default='./.cache', help='cache directory, default: ./.cache')
    parser.add_argument('-nc',  '--no-clean', action='store_true', help='do not clean cache before starting')
    # parser.add_argument('out_dir')
    # parser.add_argument('-t', '--type', default='flat')
    parser.add_argument('--list-worlds', action='store_true', help='list available worlds from this Dynmap server and exit')
    parser.add_argument('--list-maps', action='store_true', help='list available maps for this world and exit')
    parser.add_argument('-t', '--threshold', nargs='?', default='0.01', help='threshold for timelapse images, default: 0.01')
    parser.add_argument('-q', '--quiet', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-vv', '--verbose-debug', action='store_true')

    args = parser.parse_args()


    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    if args.verbose_debug:
        logging.basicConfig(level=logging.DEBUG)

    logging.debug('args: %s', str(args))

    if args.image_format not in ['png', 'jpg', 'webp']:
        logging.error('Only png, jpg and webp are supported')
        sys.exit(1)

    dm = dynmap.DynMap(args.base_url, args.image_format)

    if args.list_worlds:
        worlds = dm.worlds
        logging.info('Available worlds: %s', str(worlds))
        for name in worlds.keys():
            print('%s - %s' % (name, worlds[name].title))
        sys.exit(0)

    if args.world:
        if not args.world:
            logging.error('No world set, use: dynmap-timemachine.py http://dynmap-address world_name')
            sys.exit(1)
        if args.world not in dm.worlds.keys():
            logging.error('This world doesn\'t exist.\nAvailable worlds: %s', dm.worlds.keys())
            sys.exit(1)

        if args.list_maps:
            logging.info('Available maps for world "%s": %s', args.world, dm.worlds[args.world].maps)
            maps = dm.worlds[args.world].maps
            for name in maps.keys():
                print('%s - %s' % (name, maps[name].title))
            sys.exit(0)

    if args.world and args.map and args.center and args.boundary_size and args.dest and args.zoom and args.threads:
        maps = dm.worlds[args.world].maps

        if int(args.threads) < 1:
            logging.error('Threads must be a positive integer')
            sys.exit(1)

        if args.map not in maps.keys():
            logging.error('Map not found, use: dynmap-timemachine.py http://dynmap-address world_name map_name [x,y,z] [width,height]')
            for name in maps.keys():
                print('%s - %s' % (name, maps[name].title))
            sys.exit(1)

        center = [int(i) for i in args.center.strip('[]').split(',')]
        size = [int(i) for i in args.boundary_size.strip('[]').split(',')]
        # print(size)
        # sys.exit(-1)

        dm_map = maps[args.map]
        m_loc = projection.MinecraftLocation(center[0], center[1], center[2], dm_map.worldtomap)

        tm = time_machine.TimeMachine(dm, int(args.threads), args.cache_dir, not args.no_clean)
        dest = f"{args.dest}.{args.image_format}"
        zoom = int(args.zoom)
        img = tm.capture_single(dm_map, m_loc.to_tile_location(zoom), size)

        if os.path.isdir(dest):
            files = list(glob.iglob(os.path.join(dest, f'*.{args.image_format}')))
            difference = 0
            if files:
                newest_image = max(files, key=os.path.getctime)
                difference = tm.compare_images(Image.open(newest_image), img)
                threshold = float(args.threshold)

            if not files or difference >= threshold:
                dest = os.path.join(dest, time.strftime('%Y-%m-%d %H-%M-%S') + '.' + args.image_format)
                img.save(dest)
                logging.info('Saving timelapse image to "%s" (%d KB) with difference %.2f', dest, os.path.getsize(dest) / 1000, difference * 100)
        else:
            img.save(dest)
            logging.info('Saving image to "%s" (%d KB)', dest, os.path.getsize(dest) / 1000)

        # sys.exit(0)
