# -*- coding: utf-8 -*-
"""
    Catch-up TV & More
    Copyright (C) 2017  SylvainCecchetto

    This file is part of Catch-up TV & More.

    Catch-up TV & More is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    Catch-up TV & More is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with Catch-up TV & More; if not, write to the Free Software Foundation,
    Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""

import ast
import json
import re
import os
from bs4 import BeautifulSoup as bs
from resources.lib import utils
from resources.lib import common

# TO DO
# Move WAT to resolver.py (merge with mytf1 code)

# Initialize GNU gettext emulation in addon
# This allows to use UI strings from addon’s English
# strings.po file instead of numeric codes
_ = common.ADDON.initialize_gettext()

URL_ROOT = 'https://www.%s.fr'
# ChannelName

URL_VIDEOS = 'https://www.%s.fr/videos?page=%s'
# PageId

URL_WAT_BY_ID = 'https://www.wat.tv/embedframe/%s'

URL_VIDEO_STREAM = 'https://www.wat.tv/get/webhtml/%s'

DESIRED_QUALITY = common.PLUGIN.get_setting('quality')

def channel_entry(params):
    """Entry function of the module"""
    if 'root' in params.next:
        return root(params)
    elif 'list_shows' in params.next:
        return list_shows(params)
    elif 'list_videos' in params.next:
        return list_videos(params)
    elif 'live' in params.next:
        return list_live(params)
    elif 'play' in params.next:
        return get_video_url(params)
    return None


@common.PLUGIN.mem_cached(common.CACHE_TIME)
def root(params):
    """Add Replay and Live in the listing"""
    modes = []

    # Add Replay
    modes.append({
        'label': 'Replay',
        'url': common.PLUGIN.get_url(
            action='channel_entry',
            next='list_videos_1',
            page='0',
            category='%s Replay' % params.channel_name.upper(),
            window_title='%s Replay' % params.channel_name
        )
    })

    return common.PLUGIN.create_listing(
        modes,
        sort_methods=(
            common.sp.xbmcplugin.SORT_METHOD_UNSORTED,
            common.sp.xbmcplugin.SORT_METHOD_LABEL
        ),
        category=common.get_window_title()
    )

@common.PLUGIN.mem_cached(common.CACHE_TIME)
def list_shows(params):
    return None

@common.PLUGIN.mem_cached(common.CACHE_TIME)
def list_videos(params):
    """Build videos listing"""
    videos = []
    if 'previous_listing' in params:
        videos = ast.literal_eval(params['previous_listing'])

    if params.next == 'list_videos_1':
        list_videos = utils.get_webcontent(
            URL_VIDEOS % (params.channel_name, params.page))
        list_videos_soup = bs(list_videos, 'html.parser')

        videos_data = list_videos_soup.find_all(
            'div', class_=re.compile("views-row"))


        for video in videos_data:

            title = video.find(
                'span', class_='field-content').find(
                'a').get_text()
            plot = video.find(
                'div', class_='field-resume').get_text().strip()
            duration = 0
            img = URL_ROOT % params.channel_name + \
                video.find('img').get('src')
            video_url = URL_ROOT % params.channel_name + '/' + \
                video.find('a').get('href').encode('utf-8')

            info = {
                'video': {
                    'title': title,
                    'plot': plot,
                    # 'aired': aired,
                    # 'date': date,
                    'duration': duration,
                    # 'year': year,
                    'mediatype': 'tvshow'
                }
            }

            download_video = (
                _('Download'),
                'XBMC.RunPlugin(' + common.PLUGIN.get_url(
                    action='download_video',
                    video_url=video_url) + ')'
            )
            context_menu = []
            context_menu.append(download_video)

            videos.append({
                'label': title,
                'thumb': img,
                'url': common.PLUGIN.get_url(
                    action='channel_entry',
                    next='play_r',
                    video_url=video_url,
                ),
                'is_playable': True,
                'info': info,
                'context_menu': context_menu
            })

        # More videos...
        videos.append({
            'label': common.ADDON.get_localized_string(30100),
            'url': common.PLUGIN.get_url(
                action='channel_entry',
                next='list_videos_1',
                page=str(int(params.page) + 1),
                update_listing=True,
                previous_listing=str(videos)
            )
        })

    return common.PLUGIN.create_listing(
        videos,
        sort_methods=(
            common.sp.xbmcplugin.SORT_METHOD_UNSORTED
        ),
        content='tvshows',
        update_listing='update_listing' in params,
        category=common.get_window_title()
    )

@common.PLUGIN.mem_cached(common.CACHE_TIME)
def list_live(params):
    return None

@common.PLUGIN.mem_cached(common.CACHE_TIME)
def get_video_url(params):
    """Get video URL and start video player"""

    if params.next == 'play_r' or params.next == 'download_video':
        video_html = utils.get_webcontent(params.video_url)
        video_id = re.compile(
            r'www.wat.tv/embedframe/(.*?)[\"\?]').findall(
            video_html)[0]
        url_wat_embed = URL_WAT_BY_ID % video_id
        wat_embed_html = utils.get_webcontent(url_wat_embed)

        stream_id = re.compile('UVID=(.*?)&').findall(wat_embed_html)[0]
        url_json = URL_VIDEO_STREAM % stream_id
        htlm_json = utils.get_webcontent(url_json, random_ua=True)
        json_parser = json.loads(htlm_json)

        # Check DRM in the m3u8 file
        manifest = utils.get_webcontent(
            json_parser["hls"],
            random_ua=True)
        if 'drm' in manifest:
            utils.send_notification(common.ADDON.get_localized_string(30102))
            return ''

        root = os.path.dirname(json_parser["hls"])
        manifest = utils.get_webcontent(
            json_parser["hls"].split('&max_bitrate=')[0])

        lines = manifest.splitlines()
        if DESIRED_QUALITY == "DIALOG":
            all_datas_videos_quality = []
            all_datas_videos_path = []
            for k in range(0, len(lines) - 1):
                if 'RESOLUTION=' in lines[k]:
                    if len(re.compile(
                        r'RESOLUTION=(.*?),').findall(
                        lines[k])) > 0:
                        all_datas_videos_quality.append(
                            re.compile(
                            r'RESOLUTION=(.*?),').findall(
                            lines[k])[0])
                    else:
                        all_datas_videos_quality.append(
                            lines[k].split('RESOLUTION=')[1])
                    all_datas_videos_path.append(
                        root + '/' + lines[k + 1])
            seleted_item = common.sp.xbmcgui.Dialog().select(
                _('Choose video quality'),
                all_datas_videos_quality)
            return all_datas_videos_path[seleted_item].encode(
                'utf-8')
        elif DESIRED_QUALITY == 'BEST':
            # Last video in the Best
            for k in range(0, len(lines) - 1):
                if 'RESOLUTION=' in lines[k]:
                    url = root + '/' + lines[k + 1]
            return url
        else:
            for k in range(0, len(lines) - 1):
                if 'RESOLUTION=' in lines[k]:
                    url = root + '/' + lines[k + 1]
                break
            return url
