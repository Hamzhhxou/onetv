import argparse
import pprint
import json
import shutil
import os.path

import config_factory
import site_config
from lib import data_loader
from lib import json_helper
from lib import sitemap_helper
from lib import util
from lib import yt_api_util
from lib.api import ApiDataLoader
from lib.data_loader import *
from lib.html_helper import HtmlHelper
from lib.model import SiteConfig, PageConfig, Site
from multiprocessing import Pool

html_helper = HtmlHelper()

def open_out_file(out_dir, name):
    return open("%s/%s" % (out_dir, name), "w")

def day_pages(site, config):
    pages = []
    for day in site.groups_by_day:
        path = util.day_page_path(day)
        page_config = PageConfig()
        page_config.title = "%s | Spark AR TV" % day.title
        page_config.description = config.site_config.page_config.description
        if util.banner_generated(config.out_dir, day):
            page_config.og_image = util.get_group_banner_url(config, day)
        else:
            page_config.og_image = util.get_logo_url(config)

        pages.append((path, html_helper.gen_week_html(site, page_config, day)))
    return pages
        

def week_pages(site, config):
    pages = []
    for week in site.groups_by_week:
        path = util.week_page_path(week)
        page_config = PageConfig()
        page_config.title = "%s | Spark AR TV" % week.title
        page_config.description = config.site_config.page_config.description
        if util.banner_generated(config.out_dir, week):
            page_config.og_image = util.get_group_banner_url(config, week)
        else:
            page_config.og_image = util.get_logo_url(config)

        pages.append((path, html_helper.gen_week_html(site, page_config, week)))
    return pages

def standard_pages(site, config):
    page_config = PageConfig(config.site_config.page_config)
    page_config.og_image = util.get_logo_url(config)
    
    pages = [
        ("index.html", html_helper.gen_timeline_html(site, page_config)),
        ("full-list.html", html_helper.gen_timeline_html(site, page_config, full=True)),
        #("debug.html", html_helper.gen_debug_html(site, page_config)),
    ]
    pages.append(("channels.html", html_helper.gen_channels_html(site, page_config)))
    return pages

def topic_pages(site, config):
    if not site.topics:
        return []
    pages = []
    for topic in site.topics:
        path = util.topic_page_path(topic)
        page_config = PageConfig()
        page_config.title = "%s | Spark AR TV" % topic.title
        page_config.description = config.site_config.page_config.description
        if util.topic_banner_generated(config.out_dir, topic):
            page_config.og_image = util.get_topic_banner_url(config, topic)
        else:
            page_config.og_image = util.get_logo_url(config)

        featured = None
        title = None
        if len(topic.ids) > 12:
            title = topic.title
            featured_ids = data_loader.sort_by_view_count(topic.ids, site.video_data)
            featured = Group("Featured", featured_ids[:6])
            topic = Group("All videos", topic.ids)
        pages.append((
            path, 
            html_helper.gen_topic_html(
                site, page_config, topic, featured, title)))
    return pages

def facebook_pages(site, config):
    page_config = PageConfig()
    page_config.title = "Facebook | Spark AR TV"
    page_config.description = config.site_config.page_config.description
    return [("facebook.html", html_helper.gen_facebook_html(site, page_config))]

def interviews_pages(site, config):
    page_config = PageConfig(config.site_config.page_config)
    page_config.title = "Interviews | Spark AR TV"
    if site.interviews:
        page_config.og_image = util.get_group_banner_url(config, site.interviews[0])
    return [("interviews.html", html_helper.gen_interviews_html(site, page_config))]

def custom_pages(site, config):
    pages = []
    for x in site.custom:
        page_config = PageConfig(config.site_config.page_config)
        page_config.title = "%s | Spark AR TV" % x['title']

        pages.append((
            "%s.html" % x['slug'], 
            html_helper.gen_fb_videos_html(site, page_config, x)
        ))
    return pages

def blogs(site, config):
    pages = []
    for x in site.blogs:
        page_config = PageConfig(config.site_config.page_config)
        page_config.title = "%s | Spark AR TV" % x['title']
        page_config.og_image = util.get_blog_banner_url(config, x['slug'])
        pages.append((
            "blogs/%s.html" % x['slug'], 
            html_helper.gen_blog_html(site, page_config, x)
        ))
    return pages

def single_channel_pages(site, config, groups):
    for x in groups:
        first_vid = site.video_data[x.ids[0]]
        channel_id = first_vid.channel_id
        page_config = PageConfig(config.site_config.page_config)
        page_config.title = "%s | Spark AR TV" % x.title
        if util.channel_banner_generated(config.out_dir, channel_id):
            page_config.og_image = util.get_channel_banner_url(config, channel_id)
        else:
            page_config.og_image = util.get_logo_url(config)
        
        path = "channels/%s.html" % channel_id
        html = html_helper.gen_single_channel_html(site, page_config, x)
       
        out_dir = "%s/global" % (config.out_dir)
        with open_out_file(out_dir, path) as outfile:
            outfile.write(html)
            print("Generated %s" % outfile.name)

def sitemap_page(master, site, config):
    page_config = PageConfig(config.site_config.page_config)
    page_config.title = "Sitemap | Spark AR TV" 
    page_config.og_image = util.get_logo_url(config)
    sitemap = sitemap_helper.load_sitemap(master, config)
    page = ("sitemap.html", html_helper.gen_sitemap_html(site, page_config, sitemap))
    return page

def search_page(master, site, config):
    page_config = PageConfig(config.site_config.page_config)
    page_config.title = "Search | Spark AR TV" 
    page_config.og_image = util.get_logo_url(config)
    sitemap = sitemap_helper.load_sitemap(master, config)
    page = ("search.html", html_helper.gen_search_html(site, page_config, sitemap))
    return page

def gen_lang_site(master, site, config):
    lang = site.lang
    out_dir = "%s/%s" % (config.out_dir, lang)
    util.mkdir(out_dir)
    util.mkdir("%s/weeks" % out_dir)
    util.mkdir("%s/days" % out_dir)

    pages = standard_pages(site, config)
    if not config.index_only:
        pages += week_pages(site, config)
        pages += day_pages(site, config)

        if site.topics:
            util.mkdir("%s/topics" % out_dir)
            pages += topic_pages(site, config)
        if site.facebook:
            pages += facebook_pages(site, config)
        if site.interviews:
            pages += interviews_pages(site, config)
        if site.custom:
            pages += custom_pages(site, config)
        if site.blogs:
            util.mkdir("%s/blogs" % out_dir)
            pages += blogs(site, config)
        if site.gen_sitemap:
            pages += [sitemap_page(master, site, config)]
        if site.gen_search:
            pages += [search_page(master, site, config)]

    for page in pages:
        with open_out_file(out_dir, page[0]) as outfile:
            outfile.write(page[1])
            print("Generated %s" % outfile.name)

def gen_global_json(master):
    config = master.config
    site = master.global_site

    pages = [
        ('nav.json', json_helper.nav_json(master, indent = 2)),
        ('nav.min.json', json_helper.nav_json(master)),
        ('search.json', json_helper.search_json(master))
    ]
    out_dir = "%s/global" % (config.out_dir)
    for page in pages:
        with open_out_file(out_dir, page[0]) as outfile:
            outfile.write(page[1])
            print("Generated %s" % outfile.name)

def gen_global_site(master):
    config = master.config
    site = master.global_site

    gen_lang_site(master, site, config)

def pool_gen_global_site_channels(pool, master):
    config = master.config
    site = master.global_site

    pages = []
    out_dir = "%s/global" % (config.out_dir)
    results = []
    if site.gen_channel_html and config.channel:
        util.mkdir("%s/channels" % out_dir)
        chunks = util.chunks(site.groups, 10)
        for chunk in chunks:
            results.append(pool.apply_async(single_channel_pages, (site, config, chunk)))
    return results

def gen_site(config):
    master = master_site(config)

    html_helper.master = master
    html_helper.config = config
    html_helper.global_site = master.global_site
  
    if config.global_only:
        langs = []
    else:
        langs = config.site_config.languages

    with Pool(processes=3) as pool:
        results = []
        results += pool_gen_global_site_channels(pool, master)
        results += [
            pool.apply_async(gen_global_site, (master,)),
            pool.apply_async(gen_global_json, (master,)),
        ]
        results += [pool.apply_async(gen_lang_site, (master, master.lang_sites[lang], config)) for lang in langs]
        [res.get(timeout=60) for res in results]

    # Copy assets
    util.copy_all_assets(config)

def main(args):
    prod = args.prod
    assets_only = args.assets
    index_only = args.index_only
    global_only = args.global_only or index_only
    channel = args.channel or prod
    validate = args.validate

    util.prepare_cache()

    config = config_factory.load(prod)
    config.global_only = global_only
    config.index_only = index_only
    config.channel = channel

    if assets_only:
        util.copy_all_assets(config)
    elif validate:
        video_cache = data_loader.load_cache()
        data_loader.load_global_groups(config, video_cache)
    else:
        gen_site(config)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Site generation')
    parser.add_argument('--prod', action='store_true')
    parser.add_argument('--assets', action='store_true')
    parser.add_argument('--global-only', action='store_true')
    parser.add_argument('--index-only', action='store_true')
    parser.add_argument('--channel', action='store_true')
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()
    main(args)
