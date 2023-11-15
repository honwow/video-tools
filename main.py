import os
import json
import requests
import re
import csv
import time
import yagmail
from lxml import etree
import schedule
import configparser
import xml.etree.ElementTree as et
from xml.dom import minidom
from tmdbv3api import TMDb, Find, Season, TV
import glob
import chardet
import codecs
import sys
import datetime

init_path = "/config/config.ini"
csv_path = "/config/data.csv"
downloads_tv_folder = "/data/Downloads/电视剧/"
downloads_mv_folder = "/data/Downloads/电影/"
video_tv_folder = "/data/Videos/电视剧/"
video_mv_folder = "/data/Videos/电影/"
rss_url = []  # rss link
admin_email = ""
email_list = ''
url_qb = ""
user_qb = ""
passwd_qb = ""
url_tpb = "https://piratebay.live"
url_btzj = "https://www.btbtt12.com"
interval = 4
sender_email_token = ""
sender_email_user = ""
sender_email_host = ""
video_weight = ""
tmdb_key = ""
download_speed_flag = ""
download_percentage_flag = ""

session = requests.session()
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"}
video_type = [".mp4", ".mkv", ".mov", ".flv", ".avi", ".rmvb", ".rm"]


def send_email(to, email_title, email_content):
    if to and sender_email_user:
        server = yagmail.SMTP(user=sender_email_user, password=sender_email_token, host=sender_email_host)
        server.send(to, email_title, email_content)
        server.close()


def get_html(url, email_title):
    result = ""
    email_content = ""
    try:
        response = requests.get(url=url, headers=headers)
    except:
        send_email(admin_email, email_title, email_content)
        return result
    else:
        if response.status_code != 200:
            send_email(admin_email, email_title, email_content)
        else:
            result = response.text
        return result


def write_csv(csv_file, txt_list, mode):
    with open(csv_file, mode=mode, encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(txt_list)


def read_csv(csv_file):
    result = []
    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for r in reader:
            result.append(r)
    return result


def get_rss_info(rss_link):
    rss_info = []
    email_title = "错误，豆瓣访问错误"
    rss_result = get_html(rss_link, email_title)
    if rss_result:
        pattern_title = re.compile("<title>想看(.*?)</title>")
        video_titles = re.findall(pattern_title, rss_result)
        if video_titles:
            pattern_link = re.compile("<link>(.*?)</link>")
            video_links = re.findall(pattern_link, rss_result)[1:]
            pattern_date = re.compile("<pubDate>(.*?)</pubDate>")
            added_dates = re.findall(pattern_date, rss_result)[1:]
            gmt_format = '%a, %d %b %Y %H:%M:%S GMT'
            for i in range(len(video_titles)):
                added_date = datetime.datetime.strptime(added_dates[i], gmt_format) + datetime.timedelta(hours=8)
                if added_date.date() == datetime.datetime.today().date():
                    rss_info.append([video_titles[i], video_links[i]])
    return rss_info


def get_html_value(html_tree, text):
    res = html_tree.xpath(text)
    if res:
        result = res[0]
    else:
        result = ""
    return result


def search_video_douban(video_title, url):
    video_info = []
    nfo_info = []
    email_title = "错误，豆瓣访问错误"
    html_txt = get_html(url, email_title)
    if html_txt:
        html_tree = etree.HTML(html_txt)
        # get video information
        mixed_title = get_html_value(html_tree, '//*[@id="content"]/h1/span[1]/text()')
        if not mixed_title:
            mixed_title = video_title
        year_d = get_html_value(html_tree, '//*[@id="content"]/h1/span[2]/text()')
        season_flag = re.search("第(.*?)季", mixed_title)
        if season_flag:
            season_d = re.findall(r'\d+', mixed_title)[-1]
            season_format = "{:0>2d}".format(int(season_d))
            season_span = season_flag.span()
            o_title_d = mixed_title[season_span[1] + 1:-9].strip() + " " + year_d + " S" + str(season_format)
            title_d = mixed_title[:season_span[0]].strip() + " " + year_d + " S" + str(season_format)
        else:
            title_d = video_title + " " + year_d
            o_title_d = mixed_title[re.search(video_title, mixed_title).span()[1]:].strip()
            if not o_title_d:
                o_title_d = title_d
            else:
                o_title_d = o_title_d + " " + year_d
            season_d = ""

        # 如果是日韩电影，则原名称等于中文名称
        jap = re.compile(r'[\u3034-\u309F\u30A0-\u30FF\uAC00-\uD7A3]')
        jap_search = jap.search(mixed_title)
        if jap_search:
            o_title_d = title_d

        pattern_episode = re.compile(r'<span class="pl">集数:</span>(.*?)<br/>')
        episodes = re.findall(pattern_episode, html_txt)
        if episodes:
            episode_d = episodes[0].strip()
            if not season_d:
                season_d = 1
                title_d = title_d + " S01"
                o_title_d = o_title_d + " S01"
            else:
                season_d = season_d
        else:
            episode_d = ""
            season_d = ""

        sub_flag = 0
        if title_d != o_title_d:
            sub_flag = 1
        video_info = [title_d, o_title_d, season_d, episode_d, sub_flag]

        # nfo信息---------------------------------------nfo信息
        rating = get_html_value(html_tree, '//strong[@class="ll rating_num"]/text()')
        voting = get_html_value(html_tree, '//span[@property="v:votes"]/text()')
        # plot
        movie_sum = html_tree.xpath('//span[@property="v:summary"]/text()')
        plot = ""
        if movie_sum:
            for item in movie_sum:
                plot += item.strip()
        # poster&fan art
        post_url = url + "photos?type=R"
        html_poster = get_html(post_url, email_title)
        fanart1 = []
        poster1 = []
        poster = ""
        fanart = ""
        if html_poster:
            poster_tree = etree.HTML(html_poster)  # get etree instance
            poster_url = poster_tree.xpath('//ul[@class="poster-col3 clearfix"][1]/li')
            for item in poster_url:
                resolution1 = get_html_value(item, "./div[2]/text()")
                resolution2 = resolution1.split("x")
                image_url = get_html_value(item, "./div[1]/a/img/@src")
                if int(resolution2[0].strip()) > int(resolution2[1].strip()):
                    fanart1.append(image_url)  # get fanart by resolution comparing, no language specified
                else:
                    poster_txt = get_html_value(item, './div[3]/text()')
                    if "中国大陆" in poster_txt:  # get poster with language specified
                        poster1.append(image_url)
                if len(fanart1) >= 1 and len(poster1) >= 1:  # if fanart and post is found, jump out
                    break
            if poster1:
                poster = poster1[0]
            else:
                poster = get_html_value(poster_tree, '//ul[@class="poster-col3 clearfix"][1]/li[1]/div[1]/a/img/@src')
            if fanart1:
                fanart = fanart1[0]
            else:
                fanart = ""
        findcountry = '<span class="pl">制片国家/地区:</span>(.*?)<br/>'
        country = re.findall(findcountry, html_txt, re.S)[0].strip()
        premier = get_html_value(html_tree, '//span[@property="v:initialReleaseDate"]/text()')
        premier = premier[:10]
        genre = html_tree.xpath('//span[@property="v:genre"]/text()')
        crew = get_html_value(html_tree, '//*[@id="info"]/span[2]/span[2]/a[1]/text()')
        director = get_html_value(html_tree, '//a[@rel="v:directedBy"]/text()')
        # get movie actors pictures, and save to local file, the path = img_filepath
        crew_url = html_tree.xpath('//ul[@class="celebrities-list from-subject __oneline"]/li')
        actors = []
        for j in range(1, len(crew_url)):  # start from 2nd data, the fisrt is director information
            item = crew_url[j]
            role1 = get_html_value(item, './div//span[@class="role"]/text()')
            if "导演" not in role1:
                actor = get_html_value(item, './a/@title')
                role = role1[2:]
                actor_url = get_html_value(item, './a/div/@style')
                actor_url = actor_url[22:-1]
                actors.append([actor, role, actor_url])
            if j == 8:  # only get 5 actors information
                break
        find_lau = '<span class="pl">语言:</span>(.*?)<br/>'
        lau = re.findall(find_lau, html_txt, re.S)[0].strip()

        tv_title = title_d[:re.search(r"\(\d{4}", title_d).span()[0]].strip()
        tv_o_title = o_title_d[:re.search(r"\(\d{4}", o_title_d).span()[0]].strip()
        imdb_id = ""
        if episodes:
            find_runtime = '<span class="pl">单集片长:</span>(.*?)<br/>'
            runtime_flag = re.findall(find_runtime, html_txt, re.S)
            if runtime_flag:
                runtime = runtime_flag[0].replace("分钟", "").strip()
            else:
                runtime = "不详"
            find_imdb = '<span class="pl">IMDb:</span>(.*?)<br>'
            imdb_id_info = re.findall(find_imdb, html_txt, re.S)
            if imdb_id_info:
                imdb_id = imdb_id_info[0]
        else:
            runtime = get_html_value(html_tree, '//span[@property="v:runtime"]/@content')
            if not runtime:
                runtime = "不详"

        nfo_info = [tv_title, tv_o_title, year_d, rating, voting, plot, runtime, poster, fanart, country, premier,
                    genre,
                    director, actors, lau, season_d, imdb_id, crew]
    return video_info, nfo_info


def modify_host_file():
    hosts_content = []
    i = 0
    ips = []
    while i < 5:
        i += 1
        ips = get_tmdb_ip_ip33()
        if ips:
            break
        else:
            ips = get_tmdb_ip_myssl()
            if ips:
                break
            else:
                time.sleep(30)

    if ips:
        host_file = "/etc/hosts"
        with open(host_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                if not ("api.themoviedb.org" in line):
                    hosts_content.append(line)

        for ip in ips:
            text = ip + "\t" + "api.themoviedb.org" + "\n"
            hosts_content.append(text)

        with open(host_file, "w+", encoding="utf-8") as f:
            f.writelines(hosts_content)


def get_tmdb_ip_myssl():
    url = "https://myssl.com/api/v1/tools/dns_query?qtype=1&host=api.themoviedb.org&qmode=-1"
    try:
        result = requests.get(url=url, headers=headers).text
    except:
        return ""
    else:
        ips = re.findall("\d+\.\d+\.\d+\.\d+", result)
        if ips:
            return ips
        else:
            return ""


def get_tmdb_ip_ip33():
    url = "http://api.ip33.com/dns/resolver"
    domain = "api.themoviedb.org"
    dns = ['156.154.70.1', '208.67.222.222']
    ip_list = []
    for d in dns:
        try:
            result = requests.post(url=url, data={'domain': domain, 'type': 'A', 'dns': d}, headers=headers).text
        except:
            return ""
        else:
            ips = re.findall("\d+\.\d+\.\d+\.\d+", result)
            if ips:
                for i in range(1, len(ips)):
                    ip_list.append(ips[i])

    return ip_list


def search_tmdb(video_title, imdb_id, video_season):
    info = []
    tmdb_id = ''
    img_url = r"https://image.tmdb.org/t/p/original"
    try:
        tmdb = TMDb()
        tmdb.api_key = tmdb_key
        tmdb.language = 'zh-CN'
        find_video = Find()
        season_tv = Season()
        tv_search = TV()
        results = find_video.find(imdb_id, "imdb_id")
        if results:
            tv = results["tv_results"]
            epi = results["tv_episode_results"]
            if tv:
                tmdb_id = tv[0]["id"]
            elif epi:
                if 'show_id' in epi[0].keys():
                    tmdb_id = epi[0]["show_id"]
                else:
                    tv_result = tv_search.search(video_title)
                    for t in tv_result:
                        if video_title.lower() == t["original_name"].lower():
                            tmdb_id = t["id"]
                            break
            else:
                tmdb_id = ""

            if tmdb_id:
                results_epi = season_tv.details(tmdb_id, video_season)
                if results_epi:
                    details = results_epi["episodes"]
                    if details:
                        for detail in details:
                            epi_title = detail["name"]
                            epi_no = detail["episode_number"]
                            epi_rating = detail["vote_average"]
                            epi_voting = detail["vote_count"]
                            epi_plot = detail["overview"]
                            if detail["still_path"]:
                                epi_poster = img_url + detail["still_path"]
                            else:
                                epi_poster = ""
                            epi_premier = detail["air_date"]
                            info.append([epi_title, epi_no, epi_rating, epi_voting, epi_plot, epi_poster, epi_premier])
    except:
        info = []

    return info


def write_sub_element(root, tag, text):
    ele = et.SubElement(root, tag)
    ele.text = text
    return ele


def write_nfo(info, nfo_file_path):
    if not info[15]:
        root = et.Element("movie")  # 定义根节点
    else:
        root = et.Element("tvshow")  # 定义根节点

    write_sub_element(root, "title", info[0])
    write_sub_element(root, "originaltitle", info[1])
    write_sub_element(root, "sorttitle", "")
    write_sub_element(root, "epbookmark", "")
    year = info[2].replace("(", "").replace(")", "").strip()
    write_sub_element(root, "year", year)
    ratings = write_sub_element(root, "ratings", "")
    rating = write_sub_element(ratings, "rating", "")
    rating.set("default", "true")
    rating.set("max", "10")
    rating.set("name", "豆瓣")
    write_sub_element(rating, "value", info[3])
    write_sub_element(rating, "votes", info[4])
    write_sub_element(root, "plot", info[5])
    write_sub_element(root, "outline", info[5])
    write_sub_element(root, "runtime", info[6])
    poster1 = write_sub_element(root, "thumb", info[7])
    poster1.set("aspect", "poster")
    if info[15]:
        for i in range(1, int(info[15]) + 1):
            season_str = "第 " + str(i) + " 季"
            season = write_sub_element(root, "namedseason", season_str)
            season.set("number", str(i))
    fanart1 = write_sub_element(root, "fanart", "")
    write_sub_element(fanart1, "thumb", info[8])
    write_sub_element(root, "country", info[9])
    write_sub_element(root, "premiered", info[10])
    write_sub_element(root, "watched", "false")
    for item in info[11]:
        write_sub_element(root, "genre", item)
    write_sub_element(root, "director", info[12])
    write_sub_element(root, "credits", info[17])
    for item in info[13]:
        actor = write_sub_element(root, "actor", "")
        write_sub_element(actor, "name", item[0])
        write_sub_element(actor, "role", item[1])
        write_sub_element(actor, "thumb", item[2])
    write_sub_element(root, "languages", info[14])

    rawtext = et.tostring(root)
    dom = minidom.parseString(rawtext)
    nfo_folder_path = os.path.dirname(nfo_file_path)
    if not os.path.exists(nfo_folder_path):
        os.makedirs(nfo_folder_path)
    with open(nfo_file_path, 'w', encoding='utf-8') as f:
        dom.writexml(f, "", "\t", "\n", "utf-8")
        f.close()


def write_episode_nfo(info, nfo_file_path):
    # info [esp_title,tv_title1,season,episode3,rating,voting5,plot,runtime7,poster,premier,director,crew11]
    root = et.Element("episodedetails")  # 定义根节点
    write_sub_element(root, "title", info[0])
    write_sub_element(root, "originaltitle", "")
    write_sub_element(root, "showtitle", info[1])
    write_sub_element(root, "season", str(info[2]))
    write_sub_element(root, "episode", str(info[3]))
    write_sub_element(root, "displayseason", '-1')
    write_sub_element(root, "displayepisode", '-1')
    ratings = write_sub_element(root, "ratings", "")
    rating = write_sub_element(ratings, "rating", "")
    rating.set("default", "true")
    rating.set("max", "10")
    rating.set("name", "豆瓣")
    write_sub_element(rating, "value", str(info[4]))
    write_sub_element(rating, "votes", str(info[5]))
    write_sub_element(root, "plot", info[6])
    write_sub_element(root, "runtime", str(info[7]))
    write_sub_element(root, "thumb", info[8])
    write_sub_element(root, "premiered", info[9])
    write_sub_element(root, "aired", info[9])
    write_sub_element(root, "watched", "false")
    write_sub_element(root, "director", info[10])
    write_sub_element(root, "credits", info[11])

    rawtext = et.tostring(root)
    dom = minidom.parseString(rawtext)
    with open(nfo_file_path, 'w', encoding='utf-8') as f:
        dom.writexml(f, "", "\t", "\n", "utf-8")
        f.close()


def check_xml_info(root, tag):
    try:
        text = root.getElementsByTagName(tag)[0].firstChild.data
    except:
        text = ""
    return text


def get_xml_info(path):
    dom = minidom.parse(path)
    root = dom.documentElement
    title = check_xml_info(root, 'title')
    rating = check_xml_info(root, 'value')
    voting = check_xml_info(root, 'votes')
    runtime = check_xml_info(root, 'runtime')
    poster = check_xml_info(root, 'thumb')
    premier = check_xml_info(root, 'premiered')
    director = check_xml_info(root, 'director')
    crew = check_xml_info(root, 'credits')
    year = check_xml_info(root, 'year')
    xml_info = [title, rating, voting, runtime, poster, premier, director, crew, year]
    return xml_info


def get_video_info():
    csv_info = []
    if os.path.exists(csv_path):
        csv_info = read_csv(csv_path)
    for r in rss_url:
        rss_info = get_rss_info(r)  # [video_title,video_link,video_category]
        if rss_info:
            for rss in rss_info:
                if not os.path.exists(csv_path):
                    info_db, nfo_info = search_video_douban(rss[0], rss[1])  # 改0612
                    if info_db:
                        if not info_db[2]:
                            video_link = 0
                            video_folder = os.path.join(downloads_mv_folder, info_db[0])  # 0625
                            nfo_path = os.path.join(video_folder, info_db[0] + '.nfo')
                        else:
                            video_link = ",".join(['0'] * (int(info_db[3])))
                            title = re.sub(r"S\d{2}", "", info_db[0]).strip()
                            video_folder = os.path.join(downloads_tv_folder, title, 'Season ' + str(info_db[2]))
                            nfo_path = os.path.join(downloads_tv_folder, title, 'tvshow.nfo')
                        write_nfo(nfo_info, nfo_path)
                        video_info = [info_db[0], info_db[1], info_db[2], info_db[3], nfo_info[16], video_link, rss[1],
                                      video_folder, info_db[4], ""]
                        write_csv(csv_path, [video_info], "w")
                        csv_info = read_csv(csv_path)
                else:
                    csv_flag = 0
                    for i in range(len(csv_info)):
                        c = csv_info[i]
                        if rss[1] == c[6]:
                            csv_flag = 1
                            break

                    if csv_flag == 0:
                        # [title_d, o_title_d, season_d, episode_d]
                        info_db, nfo_info = search_video_douban(rss[0], rss[1])
                        time.sleep(5)
                        if info_db:
                            if not info_db[2]:
                                video_link = 0
                                video_folder = os.path.join(downloads_mv_folder, info_db[0])  # 0625
                                nfo_path = os.path.join(video_folder, info_db[0] + '.nfo')
                            else:
                                video_link = ",".join(['0'] * (int(info_db[3])))
                                title = re.sub(r"S\d{2}", "", info_db[0]).strip()
                                video_folder = os.path.join(downloads_tv_folder, title, 'Season ' + str(info_db[2]))
                                nfo_path = os.path.join(downloads_tv_folder, title, 'tvshow.nfo')
                            write_nfo(nfo_info, nfo_path)
                            video_info = [info_db[0], info_db[1], info_db[2], info_db[3], nfo_info[16], video_link,
                                          rss[1], video_folder, info_db[4], ""]
                            write_csv(csv_path, [video_info], "a")


def download_video(title, o_title, season, epi_status, video_folder, dl_links):
    pattern = re.compile(r'[\u4e00-\u9fa5]')
    cn = pattern.search(o_title)
    if cn:
        if not season:
            epi_status, dl_links = get_movie_btzj(title, epi_status, video_folder, dl_links)
        else:
            epi_status, dl_links = get_tv_btzj(title, epi_status, video_folder, dl_links)

    else:
        if not season:
            epi_status, dl_links = get_movie_tpb(title, o_title, epi_status, video_folder, dl_links)
        else:
            epi_status, dl_links = get_tv_tpb(title, o_title, season, epi_status, video_folder, dl_links)
    return epi_status, dl_links


def get_movie_btzj(title, epi_status, folder, epi_dl_link):
    search_flag = 0
    if epi_dl_link:
        ok_flag = download_video_qb(title, epi_status, epi_dl_link, folder)
        if ok_flag:
            epi_status[0] = 1
            search_flag = 1
        epi_dl_link = ""

    if search_flag == 0:
        search_title = title.replace("(", "").replace(")", "")
        search_url = url_btzj + r"/search-index-keyword-%s.htm" % search_title
        email_title = "错误，BT之家访问错误"
        html_txt = get_html(search_url, email_title)
        if html_txt:
            pattern_detailed_links = re.compile(r'<a href=(.*?)class.*?target')
            detailed_links = re.findall(pattern_detailed_links, html_txt)
            pattern_detailed_titles = re.compile(r'class="subject_link.*?title=(.*?)>')
            detailed_titles = re.findall(pattern_detailed_titles, html_txt)
            if detailed_titles and detailed_links:
                page_links = []
                for i in range(len(detailed_titles)):
                    detail = detailed_titles[i].lower()
                    if "1080p" in detail or "2160p" in detail or "720p" in detail:
                        if "web" in detail or "blu" in detail or "bd" in detail or "br" in detail:
                            if "2160p" in detail or "4K" in detail or "4k" in detail:
                                weight = video_weight[0]
                            elif "1080p" in detail:
                                weight = video_weight[1]
                            else:
                                weight = video_weight[2]
                            detailed_link = url_btzj + "/" + detailed_links[i].strip().replace('"', "")
                            page_links.append([detailed_link, weight])

                if page_links:
                    page_links = sorted(page_links, key=lambda k: k[1], reverse=True)
                    ok_flag = 0
                    for i in range(len(page_links)):
                        html_txt_movie = get_html(page_links[i][0], email_title)
                        if html_txt_movie:
                            pattern_download_url = re.compile(r'<a href="attach-dialog(.*?)target')
                            url_dl = re.findall(pattern_download_url, html_txt_movie)
                            if url_dl:
                                dl_link = url_btzj + "/attach-download" + url_dl[0].strip().replace('"', "")
                                if ok_flag == 0:
                                    ok_flag = download_video_qb(title, epi_status, dl_link, folder)
                                    if ok_flag:
                                        epi_status[0] = 1
                                else:
                                    epi_dl_link = dl_link
                                    break

    return epi_status, epi_dl_link


def get_tv_btzj_detail(start, end, link):
    torrent_links = []
    epi_counts = []
    email_title = "错误，BT之家访问错误"
    detailed_link = url_btzj + "/" + link.strip().replace('"', "")
    html_txt_tv = get_html(detailed_link, email_title)
    if html_txt_tv:
        pattern_dl_url = re.compile(r'<a href="attach-dialog(.*?)target')
        dl_url = re.findall(pattern_dl_url, html_txt_tv)
        if len(dl_url) > 1:
            pattern_episode_no = re.compile(r'E[P]?(.*?)\..*?\.torrent')
            episode_no = re.findall(pattern_episode_no, html_txt_tv)
            if episode_no:
                for i in range(len(episode_no)):
                    e = episode_no[i]
                    epi_counts1 = e.split("-")
                    if len(epi_counts1) == 1:
                        try:
                            epi_counts1 = [int(epi_counts1[0]), int(epi_counts1[0])]
                        except:
                            pass
                        else:
                            epi_counts.append([epi_counts1, dl_url[i]])
                    else:
                        try:
                            epi_counts1 = [int(epi_counts1[0]), int(epi_counts1[1])]
                        except:
                            pass
                        else:
                            epi_counts.append([epi_counts1, dl_url[i]])

                epi_counts = sorted(epi_counts, key=lambda k: k[0])

                temp = []
                for i in range(len(epi_counts)):
                    if temp:
                        duplication_flag = 0
                        for j in range(len(temp)):
                            if epi_counts[i][0] in temp[j]:
                                duplication_flag = 1
                                break
                        if duplication_flag == 0:
                            temp.append(epi_counts[i])
                    else:
                        temp.append(epi_counts[i])

                torrent_links = list.copy(temp)
                for i in range(len(temp)):
                    for j in range(len(temp)):
                        if temp[i][0][0] >= temp[j][0][0] and temp[i][0][1] <= temp[j][0][1]:
                            if i != j:
                                if temp[i] in torrent_links:
                                    torrent_links.remove(temp[i])
        else:
            torrent_links.append([[start, end], dl_url[0]])

    return torrent_links


def get_tv_btzj(title, epi_status, folder, epi_dl_link):
    search_flag = 0
    if epi_dl_link:
        ok_flag = download_video_qb(title, epi_status, epi_dl_link, folder)
        if ok_flag:
            for i in ok_flag:
                epi_status[i - 1] = 1
            search_flag = 1
        epi_dl_link = ""

    if search_flag == 0:
        epi_dl_link = ""
        search_title = title[:re.search(r"\(\d{4}\)", title).span()[0]].strip()
        search_url = url_btzj + r"/search-index-fid-950-orderby-timedesc-daterange-0-keyword-%s.htm" % search_title
        email_title = "错误，BT之家访问错误"
        html_txt = get_html(search_url, email_title)
        if html_txt:
            pattern_detailed_links = re.compile(r'<a href=(.*?)class.*?target')
            detailed_links = re.findall(pattern_detailed_links, html_txt)
            pattern_detailed_titles = r'subject_link.*?title=(.*?)</a>'
            detailed_titles = re.findall(pattern_detailed_titles, html_txt)
            if detailed_titles and detailed_links:
                epi_season = []  # 可以下载全季
                episode_to = []  # 更新至多少集
                episode_in = []  # 第多少集
                ok_flag = 0
                for i in range(len(detailed_titles)):
                    detailed_title = detailed_titles[i].lower()
                    if not ("网盘下载" in detailed_title):
                        if re.search("全(.*?)集", detailed_title):
                            epi_season.append([detailed_title, detailed_links[i]])
                        elif re.search("更.?至(\d+)集", detailed_title):
                            try:
                                count = int(re.findall("更.?至(\d+)集", detailed_title)[0].strip())
                            except:
                                pass
                            else:
                                if epi_status[count - 1] == 0:
                                    episode_to.append([detailed_title, detailed_links[i], count])
                        elif re.search("第(.*?)集", detailed_title):
                            counts = re.findall("第(.*?)集", detailed_title)[0].strip().split("-")
                            if len(counts) == 1:
                                try:
                                    count = int(counts[0].strip())
                                except:
                                    pass
                                else:
                                    if epi_status[count - 1] == 0:
                                        episode_in.append([detailed_title, detailed_links[i], [count] * 2])
                            elif len(counts) == 2:
                                try:
                                    count1 = int(counts[0].strip())
                                    count2 = int(counts[1].strip())
                                except:
                                    pass
                                else:
                                    if 0 in epi_status[count1 - 1:count2]:
                                        episode_in.append([detailed_title, detailed_links[i], [count1, count2]])

                if epi_season:
                    page_links = []
                    for s in epi_season:
                        if "web" in s[0] or "blu" in s[0] or "bd" in s[0] or "br" in s[0]:
                            weight1 = 5
                        else:
                            weight1 = 0
                        if "2160p" in s[0] or "4K" in s[0] or "4k" in s[0]:
                            weight2 = video_weight[0]
                        elif "1080p" in s[0]:
                            weight2 = video_weight[1]
                        else:
                            weight2 = video_weight[2]
                        weight = weight1 + int(weight2)
                        detailed_link = url_btzj + "/" + s[1].strip().replace('"', "")
                        page_links.append([detailed_link, weight])

                    page_links = sorted(page_links, key=lambda k: k[1], reverse=True)
                    for i in range(len(page_links)):
                        html_txt_tv = get_html(page_links[i][0], email_title)
                        if html_txt_tv:
                            pattern_download_url = re.compile(r'<a href="attach-dialog(.*?)target')
                            download_url = re.findall(pattern_download_url, html_txt_tv)
                            if len(download_url) == 1:
                                torrent_link = url_btzj + "/attach-download" + download_url[0].strip().replace('"', "")
                                if ok_flag == 0:
                                    ok_flag = download_video_qb(title, epi_status, torrent_link, folder)
                                    if ok_flag:
                                        for s in ok_flag:
                                            epi_status[s - 1] = 1
                                else:
                                    epi_dl_link = torrent_link
                                    break

                if ok_flag == 0 and (episode_in or episode_to):
                    info_epi_to = []
                    torrent_info_epi_to = []
                    if episode_to:
                        temp_epi_to = []  # 更至多少集
                        for s in episode_to:  # 更至多少集
                            temp_epi_to.append([s[2], s[1]])
                        info_epi_to = sorted(temp_epi_to, key=lambda k: k[0], reverse=True)[0]

                        for i in range(0, info_epi_to[0]):
                            if epi_status[i] == 0:
                                torrent_info_epi_to = get_tv_btzj_detail(0, info_epi_to[0], info_epi_to[1])
                                break

                    info_epi_in = []
                    if episode_in:
                        temp_epi_in = []  # 第多少集
                        for s in episode_in:  # 第多少集
                            temp_epi_in.append([s[2], s[1]])
                        info_epi_in = sorted(temp_epi_in, key=lambda k: k[0])

                    for i in range(0, len(epi_status)):
                        to_flag = 0
                        if epi_status[i] == 0:
                            if info_epi_to:
                                if i + 1 <= info_epi_to[0]:
                                    if torrent_info_epi_to:
                                        for fs in torrent_info_epi_to:
                                            if fs[0][0] <= i + 1 <= fs[0][1]:
                                                link = url_btzj + "/attach-download" + fs[1].strip().replace('"', "")
                                                ok_flag = download_video_qb(title, epi_status, link, folder)
                                                if ok_flag:
                                                    for j in ok_flag:
                                                        epi_status[j - 1] = 1
                                                        to_flag = 1
                                                    break

                            if info_epi_in and to_flag == 0:
                                for fs in info_epi_in:
                                    if fs[0][0] <= i + 1 <= fs[0][1]:
                                        page_links = get_tv_btzj_detail(fs[0][0], fs[0][1], fs[1])
                                        if len(page_links) == 1:
                                            link = url_btzj + "/attach-download" + page_links[0][1].strip().replace('"',
                                                                                                                    "")
                                            ok_flag = download_video_qb(title, epi_status, link, folder)
                                            if ok_flag:
                                                for j in ok_flag:
                                                    epi_status[j - 1] = 1
                                                break
                                        else:
                                            for t in page_links:
                                                if t[0][0] <= i + 1 <= t[0][1]:
                                                    link = url_btzj + "/attach-download" + t[1].strip().replace('"', "")
                                                    ok_flag = download_video_qb(title, epi_status, link, folder)
                                                    if ok_flag:
                                                        for j in ok_flag:
                                                            epi_status[j - 1] = 1
                                                        break

    return epi_status, epi_dl_link


def get_details_tpb(html_txt):
    video_dl_links = 0
    html_tree = etree.HTML(html_txt)  # get etree instance
    detailed_titles = html_tree.xpath('//a[@class="detLink"]/text()')
    detailed_links = html_tree.xpath('//a[@title="Download this torrent using magnet"]/@href')
    detailed_seeds1 = html_tree.xpath('//td[@align="right"]/text()')

    if detailed_titles and detailed_links:
        sort = []
        j = 0
        detailed_seeds = []
        for s in detailed_seeds1:
            j += 1
            if j % 2 != 0:
                detailed_seeds.append(s)

        for i in range(len(detailed_titles)):
            tl = detailed_titles[i].lower()
            if ("1080p" in tl or "2160p" in tl or "720p" in tl) and (
                    "web" in tl or "blu" in tl or "bd" in tl or "br" in tl):
                if not (re.findall("\.part", tl) or re.findall(" part", tl)):
                    if "2160p" in tl or "4K" in tl or "4k" in tl:
                        weight = video_weight[0]
                    elif "1080p" in tl:
                        weight = video_weight[1]
                    else:
                        weight = video_weight[2]
                    sort.append([detailed_links[i], weight, int(detailed_seeds[i])])
        if sort:
            video_dl_links = sorted(sort, key=lambda k: (k[1], k[2]), reverse=True)

    return video_dl_links


def get_movie_tpb(title, o_title, epi_status, folder, epi_dl_link):
    search_flag = 0
    if epi_dl_link:
        ok_flag = download_video_qb(title, epi_status, epi_dl_link, folder)
        if ok_flag:
            epi_status[0] = 1
            search_flag = 1
        epi_dl_link = ""

    if search_flag == 0:
        url = url_tpb + "/search/" + o_title.replace("(", "").replace(")", "")
        email_title = "错误，海盗湾访问错误"
        html_txt = get_html(url, email_title)
        if html_txt:
            download_links = get_details_tpb(html_txt)
            if download_links:
                ok_flag = 0
                for dl in download_links:
                    if ok_flag == 0:
                        ok_flag = download_video_qb(title, epi_status, dl[0], folder)
                        if ok_flag:
                            epi_status[0] = 1
                    else:
                        epi_dl_link = dl[0]
                        break

    return epi_status, epi_dl_link


def get_tv_tpb(title, o_title, season, epi_status, folder, epi_dl_link):
    search_flag = 0
    if epi_dl_link:
        ok_flag = download_video_qb(title, epi_status, epi_dl_link, folder)
        if ok_flag:
            for i in ok_flag:
                epi_status[i - 1] = 1
            search_flag = 1
        epi_dl_link = ""

    if search_flag == 0:
        search_title = o_title[:re.search(r'\(\d{4}', o_title).span()[0]].strip()
        season_tag = "S" + "{:0>2d}".format(int(season))
        email_title = "错误，海盗湾访问错误"

        # 搜索整个季文件，如果整个季的剧集存在
        search_url = url_tpb + "/search/" + search_title + " " + season_tag
        html_txt = get_html(search_url, email_title)
        if html_txt:
            download_links = get_details_tpb(html_txt)
            if download_links:
                ok_flag = 0
                for dl in download_links:
                    if ok_flag == 0:
                        ok_flag = download_video_qb(title, epi_status, dl[0], folder)
                        if ok_flag:
                            for i in ok_flag:
                                epi_status[i - 1] = 1
                    else:
                        epi_dl_link = dl[0]
                        break

            else:  # 如果没有整季下载，就搜索具体剧集
                epi_dl_link = ""
                for i in range(len(epi_status)):
                    if epi_status[i] == 0:
                        episode_tag = "E" + "{:0>2d}".format(i + 1)
                        search_url = url_tpb + "/search/" + search_title + " " + season_tag + episode_tag
                        html_txt = get_html(search_url, email_title)
                        download_links = get_details_tpb(html_txt)
                        if download_links:
                            for dl in download_links:
                                ok_flag = download_video_qb(title, epi_status, dl[0], folder)
                                if ok_flag:
                                    epi_status[i] = 1
                                    break
                        else:  # 如果没有找到下载链接，说明这一集还没有上映
                            break

    return epi_status, epi_dl_link


def download_video_qb(video_title, epi_status, download_link, folder):
    save_folder = folder.replace(folder[:re.search("Downloads", folder).span()[0] - 1], "").strip()
    if "\\" in save_folder:
        save_folder = save_folder.replace("\\", "/")
    tags = str(time.strftime("%y%m%d"))
    add_url = url_qb + "/api/v2/torrents/add"
    response = session.post(url=add_url, data={'urls': download_link, 'savepath': save_folder, "tags": tags},
                            headers=headers)
    if response.status_code != 200:
        email_title = "Qbittorret下载失败，请检查"
        content = "Qbittorret下载失败，请检查"
        send_email(admin_email, email_title, content)
        dl_flag = 0
    else:
        dl_flag = handle_torrent_content(video_title, epi_status, tags)
        delete_tag_qb(tags)

    return dl_flag


def login_qb():
    login_url_qb = url_qb + "/api/v2/auth/login"
    try:
        response = session.post(url=login_url_qb, data={'username': user_qb, 'password': passwd_qb}, headers=headers)
    except:
        send_email(admin_email, 'Qbittorrent无法连接，请检查', "")
        return 0
    else:
        if response.status_code != 200:
            send_email(admin_email, 'Qbittorrent无法连接，请检查', "")
            return 0
        else:
            return 1


def del_torrent_qb(torrent_hash, i):
    torrent_del_url = url_qb + "/api/v2/torrents/delete"
    if i != 0:
        session.post(url=torrent_del_url, data={'hashes': torrent_hash, "deleteFiles": "true"}, headers=headers)
    else:
        session.post(url=torrent_del_url, data={'hashes': torrent_hash, "deleteFiles": "false"}, headers=headers)


def handle_torrent_content(video_title, epi_status, tag):
    torrent_info_url = url_qb + "/api/v2/torrents/info"
    content_info_url = url_qb + "/api/v2/torrents/files"
    epi_info = []
    wait_flag = 0
    t_hash = ''
    t_size = 0
    while wait_flag < 100:
        wait_flag += 1
        response = session.post(url=torrent_info_url, data={"tag": tag}, headers=headers)
        results_json = json.loads(response.text)
        if not results_json:
            time.sleep(5)
        else:
            results = results_json[0]
            t_hash = results["hash"]
            t_size = results["total_size"]
            if t_size < 1:
                time.sleep(5)
            else:
                break

    if t_size > 0:
        wait_flag = 0
        while wait_flag < 100:
            wait_flag += 1
            response_content = session.post(url=content_info_url, data={"hash": t_hash}, headers=headers)
            content_result = json.loads(response_content.text)
            if (not content_result) or (not t_size):
                time.sleep(5)
            else:
                rename_flag = 0
                for r in content_result:
                    file_ext = os.path.splitext(r["name"])[-1]
                    ratio = r["size"] * len(content_result) / t_size
                    if file_ext in video_type and ratio > 0.2:
                        pattern_suffix = re.compile(r"E[P]?(\d{2})", re.I)
                        suffix = re.findall(pattern_suffix, r["name"])
                        if suffix:
                            episode_no = int(suffix[-1])
                            if epi_status[episode_no - 1] != 0:
                                unselect_torrent_content_qb(t_hash, r["index"])
                            else:
                                new_title = video_title + "E" + "{:0>2d}".format(episode_no) + " 第" + str(
                                    episode_no) + "集" + file_ext
                                rename_torrent_content_qb(t_hash, r["name"], new_title)
                                epi_info.append(episode_no)
                                rename_flag = 1

                        else:
                            new_title = video_title + file_ext
                            rename_torrent_content_qb(t_hash, r["name"], new_title)
                            epi_info.append(1)
                            rename_torrent_qb(t_hash, video_title)
                    else:
                        unselect_torrent_content_qb(t_hash, r["index"])

                epi_info = sorted(epi_info)
                if rename_flag == 1 and len(epi_info) > 1:
                    name = video_title + "E" + "{:0>2d}".format(epi_info[0]) + " - E" + "{:0>2d}".format(epi_info[-1])
                    rename_torrent_qb(t_hash, name)
                elif rename_flag == 1 and len(epi_info) == 1:
                    name = video_title + "E" + "{:0>2d}".format(epi_info[-1])
                    rename_torrent_qb(t_hash, name)
                break

    if (not epi_info) and t_hash:
        del_torrent_qb(t_hash, 1)
    return epi_info


def rename_torrent_content_qb(t_hash, old_title, new_title):
    rename_url = url_qb + "/api/v2/torrents/renameFile"
    session.post(url=rename_url, data={'hash': t_hash, 'oldPath': old_title, 'newPath': new_title}, headers=headers)


def rename_torrent_qb(t_hash, name):
    rename_url = url_qb + "/api/v2/torrents/rename"
    session.post(url=rename_url, data={'hash': t_hash, 'name': name}, headers=headers)


def unselect_torrent_content_qb(t_hash, file_id):
    url = url_qb + "/api/v2/torrents/filePrio"
    session.post(url=url, data={'hash': t_hash, 'id': file_id, 'priority': 0}, headers=headers)


def delete_tag_qb(tags):
    url = url_qb + "/api/v2/torrents/deleteTags"
    session.post(url=url, data={'tags': tags}, headers=headers)


def get_torrent_info_qb():
    torrent_info = []
    torrent_info_url = url_qb + "/api/v2/torrents/info"
    res = session.post(url=torrent_info_url, headers=headers)
    results = json.loads(res.text)
    if results:
        for r in results:
            state = r["state"]
            downloaded = r["downloaded"] / 2 ** 20
            time_active = r["time_active"]
            speed_avg = downloaded / time_active
            time_active_hour = time_active / 3600

            t_state = "下载中"
            if state == "error" or state == "missingFiles":
                t_state = "错误"  # 种子状态
            elif "up" in state.lower():
                t_state = "完成"  # 种子状态
            # 超过4小时，速度小于0.15mb
            elif time_active_hour >= 4 and speed_avg < download_speed_flag and r["progress"] < download_percentage_flag:
                t_state = "错误"  # 种子状态

            if t_state == "错误":
                del_torrent_qb(r["hash"], 1)

            elif t_state == "完成":  # 0706
                del_torrent_qb(r["hash"], 0)

            torrent_info.append([r["name"], t_state])

    return torrent_info


def handle_completed_video(video_title, season, path, epi_no):
    text = 0
    if season:
        video_folder_new = os.path.join(video_tv_folder, video_title[:-3].strip(), "Season " + str(season))
        title1 = video_title + "E" + "{:0>2d}".format(epi_no) + " 第" + str(epi_no) + "集"
        title = title1 + ".*"
    else:
        video_folder_new = os.path.join(video_mv_folder, video_title)
        title1 = video_title
        title = title1 + ".*"
    if not os.path.exists(video_folder_new):
        os.makedirs(video_folder_new)

    video_path = glob.glob(os.path.join(path, title))
    if video_path:
        for v in video_path:
            link_path = os.path.join(video_folder_new, title1 + os.path.splitext(v)[-1])
            if not os.path.exists(link_path):
                os.link(v, link_path)
                if os.path.splitext(v)[-1] != ".nfo":
                    text = 1
    return text


def handle_nfo(video_title, season, imdb_id, epi_status, video_folder, o_title, ):
    if season:
        dl_nfo_file = os.path.join(os.path.dirname(video_folder), "tvshow.nfo")
        video_nfo_folder = os.path.join(video_tv_folder, video_title[:-3].strip(), "Season " + str(season))
        video_nfo_file = os.path.join(os.path.dirname(video_nfo_folder), "tvshow.nfo")
        if not os.path.exists(video_nfo_folder):
            os.makedirs(video_nfo_folder)
        if not os.path.exists(video_nfo_file):
            os.link(dl_nfo_file, video_nfo_file)

        epi_nfo_flag = 0
        # [title, rating, voting2, runtime, poster4, premier, director6, crew, year]
        xml_info = get_xml_info(dl_nfo_file)
        if imdb_id:
            imdb_id = imdb_id.strip()
            # [epi_title, epi_no, epi_rating, epi_voting3, epi_plot, epi_poster5, epi_premier]
            info_tmdb = search_tmdb(o_title[:-10].strip(), imdb_id, season)
            if info_tmdb:
                epi_nfo_flag = 1
                for i in range(len(epi_status)):
                    if epi_status[i] == 2:
                        epi = info_tmdb[i]
                        if not epi[2]:
                            epi[2] = xml_info[1]
                            epi[3] = xml_info[2]
                        if not epi[5]:
                            epi[5] = xml_info[4]
                        # [esp_title,tv_title1,season,episode3,rating,voting5,plot,runtime7,poster,premier,director,crew11]
                        episode_info = [epi[0], xml_info[0], season, epi[1], epi[2], epi[3], epi[4], xml_info[3],
                                        epi[5], epi[6], xml_info[6], xml_info[7]]
                        nfo_file = video_title + "E" + "{:0>2d}".format(i + 1) + " 第" + str(i + 1) + "集" + ".nfo"
                        epi_nfo_path = os.path.join(video_folder, nfo_file)
                        write_episode_nfo(episode_info, epi_nfo_path)
                        epi_nfo_link = os.path.join(video_nfo_folder, nfo_file)
                        if not os.path.exists(epi_nfo_link):
                            os.link(epi_nfo_path, epi_nfo_link)

        if epi_nfo_flag == 0:
            for i in range(len(epi_status)):
                if epi_status[i] != 0:
                    episode_info = ["", xml_info[0], season, i + 1, xml_info[1], xml_info[2], "", xml_info[3],
                                    xml_info[4], xml_info[5], xml_info[6], xml_info[7]]
                    nfo_file = video_title + "E" + "{:0>2d}".format(i + 1) + " 第" + str(i + 1) + "集" + ".nfo"
                    epi_nfo_path = os.path.join(video_folder, nfo_file)
                    write_episode_nfo(episode_info, epi_nfo_path)
                    epi_nfo_link = os.path.join(video_nfo_folder, nfo_file)
                    if not os.path.exists(epi_nfo_link):
                        os.link(epi_nfo_path, epi_nfo_link)


def convert_file_to_utf8(filename):
    content = codecs.open(filename, 'rb').read()
    source_encoding = chardet.detect(content)['encoding']
    if source_encoding != 'utf-8' and source_encoding != 'UTF-8-SIG':
        content = content.decode(source_encoding, 'ignore')
        codecs.open(filename, 'w', encoding='UTF-8-SIG').write(content)


def run_media():
    qb_flag = login_qb()
    if qb_flag == 0:
        return

    get_video_info()
    if not os.path.exists(csv_path):
        send_email(admin_email, "豆瓣访问错误导致没有data.csv文件", "")
        return
    csv_info = read_csv(csv_path)  # [title0,o_title1,season2,episode3,category4,links5]
    if not csv_info[0]:
        return

    torrent_info = get_torrent_info_qb()

    email_content_done = []
    email_content_start = []
    for c in csv_info:
        epi_states = list(map(int, c[5].split(",")))
        list_y = list.copy(epi_states)
        nfo_flag = 0
        if 1 in epi_states:
            for t in torrent_info:
                if c[0] in t[0]:
                    if t[1] == "错误" or t[1] == "完成":
                        if not c[2]:
                            if epi_states[0] == 1:
                                if t[1] == "错误":
                                    epi_states[0] = 0
                                elif t[1] == "完成":
                                    count = handle_completed_video(c[0], c[2], c[7], 0)
                                    if count:
                                        epi_states[0] = 2
                                        email_content_done.append(c[0])
                        else:
                            epi_count = re.findall(r"E(\d{2})", t[0][re.search("\(\d{4}\)", t[0]).span()[-1]:])
                            if len(epi_count) == 1:
                                count1 = int(epi_count[0])
                                count2 = int(epi_count[0])
                            elif len(epi_count) == 2:
                                count1 = int(epi_count[0])
                                count2 = int(epi_count[1])
                            if 1 in epi_states[count1 - 1:count2]:
                                for i in range(count1, count2 + 1):
                                    if t[1] == "错误":
                                        if epi_states[i - 1] == 1:
                                            epi_states[i - 1] = 0
                                    elif t[1] == "完成":
                                        count = handle_completed_video(c[0], c[2], c[7], i)
                                        if count:
                                            epi_states[i - 1] = 2
                                            nfo_flag = 1
                                            if i < 10:
                                                email_content_done.append(c[0] + "   第" + "0" + str(i) + "集")
                                            else:
                                                email_content_done.append(c[0] + "   第" + str(i) + "集")
        if nfo_flag == 1:
            handle_nfo(c[0], c[2], c[4], epi_states, c[7], c[1])

        if 0 in epi_states:
            epi_states, c[9] = download_video(c[0], c[1], c[2], epi_states, c[7], c[9])

        if (2 not in epi_states) and (0 not in epi_states) and (1 not in list_y) and (2 not in list_y):
            email_content_start.append(c[0])
        else:
            for i in range(len(epi_states)):
                if epi_states[i] == 1 and list_y[i] == 0 and c[2]:
                    if i < 9:
                        email_content_start.append(c[0] + "   第" + "0" + str(i + 1) + "集")
                    else:
                        email_content_start.append(c[0] + "   第" + str(i + 1) + "集")

        c[5] = ",".join(map(str, epi_states))
    write_csv(csv_path, csv_info, "w")

    # 发送邮件
    email_list_final = ""
    if email_list:
        email_list_final = email_list.split(",")
        for i in range(len(email_list_final)):
            email_list_final[i] = email_list_final[i].strip()

    if email_list_final:
        content_done = "\n".join(sorted(email_content_done))
        content_start = "\n".join(sorted(email_content_start))

        if content_done and content_start:
            title = "有电影完成下载" + "\n" + "有新的电影开始下载"
            content = "已经完成下载的电影：" + "\n" + content_done + "\n" + "\n" + "新开始下载的电影：" + "\n" + content_start
            send_email(email_list_final, title, content)
        elif content_done and (not content_start):
            title = "有电影完成下载" + "\n" + "没有新的电影开始下载"
            content = "已经完成下载的电影：" + "\n" + content_done
            send_email(email_list_final, title, content)
        elif content_start and (not content_done):
            title = "有新的电影开始下载" + "\n" + "没有完成下载的电影"
            content = "新开始下载的电影：" + "\n" + content_start
            send_email(email_list_final, title, content)


def init_media_flow():
    global rss_url
    global url_qb
    global user_qb
    global passwd_qb
    global sender_email_user
    global sender_email_token
    global sender_email_host
    global admin_email
    global email_list
    global interval
    global tmdb_key
    global video_weight
    global download_speed_flag
    global download_percentage_flag

    config = configparser.ConfigParser()
    if not os.path.exists(init_path):
        config.set("DEFAULT", "# 豆瓣个人兴趣rss链接，最多可放3个链接，链接以逗号分隔，必须有", "")
        config["DEFAULT"]["rss_url"] = "????"  # rss link
        config.set("DEFAULT", "# QBittorrent的地址，必须有", "")
        config["DEFAULT"]["url_qb"] = "?????"
        config.set("DEFAULT", "# QBittorrent的用户名，如果Qb设置了用户名，则必须有", "")
        config["DEFAULT"]["user_qb"] = "????"
        config.set("DEFAULT", "# QBittorrent的登录密码，如果Qb设置了密码，则必须有", "")
        config["DEFAULT"]["passwd_qb"] = "????"

        config.set("DEFAULT", "# 用于发送信息的邮箱地址", "")
        config["DEFAULT"]["sender_email_user"] = ""
        config.set("DEFAULT", "# 用于发送信息的邮箱的token", "")
        config["DEFAULT"]["sender_email_token"] = ""
        config.set("DEFAULT", "# 用于发送信息的邮箱服务器", "")
        config["DEFAULT"]["sender_email_host"] = ""
        config.set("DEFAULT", "# 用于接收一些程序错误信息的邮箱", "")
        config["DEFAULT"]["admin_email"] = ""
        config.set("DEFAULT", "# 用于接收电影下载完成信息，可以添加多个，以逗号分隔", "")
        config["DEFAULT"]["email_list"] = ""

        config.set("DEFAULT", "# 下载超过4小时，平均速度小于多少，重新下载。单位为kb", "")
        config["DEFAULT"]["download_speed_flag"] = "150"
        config.set("DEFAULT", "# 下载超过4小时，完成百分比小于多少，重新下载", "")
        config["DEFAULT"]["download_percentage_flag"] = "30"

        config.set("DEFAULT", "# 分辨率权重，分别对应（2160p，1080p，720P)，权重分别为3，2，1排列，3为优先级最高", "")
        config["DEFAULT"]["video_weight"] = "3,2,1"

        config.set("DEFAULT", "# 程序运行间隔，如每4小时运行程序搜索电影并下载，最小值为2，最大值为24", "")
        config["DEFAULT"]["interval"] = "4"

        config.set("DEFAULT", "# TMDB的token，可以不填", "")
        config["DEFAULT"]["tmdb_key"] = ""

        with open(init_path, 'w') as configfile:
            config.write(configfile)
        return 0

    else:
        convert_file_to_utf8(init_path)
        config.read(init_path, encoding="utf-8-sig")
        rss_url_tem = config.get("DEFAULT", "rss_url")
        rss_url_lists = rss_url_tem.split(",")
        if len(rss_url_lists) > 3:
            rss_url = rss_url[:3]
        elif len(rss_url_lists) == 0:
            return 0
        else:
            rss_url = rss_url_lists
        for r in rss_url:
            try:
                requests.get(url=r, headers=headers)
            except:
                send_email(admin_email, "豆瓣个人兴趣rss%s无法访问，请确认" % r, "")
                return 0
        url_qb = config.get("DEFAULT", "url_qb")
        user_qb = config.get("DEFAULT", "user_qb")
        passwd_qb = config.get("DEFAULT", "passwd_qb")
        qb_flag = login_qb()
        if qb_flag == 0:
            return 0
        sender_email_user = config.get("DEFAULT", "sender_email_user")
        sender_email_token = config.get("DEFAULT", "sender_email_token")
        sender_email_host = config.get("DEFAULT", "sender_email_host")
        admin_email = config.get("DEFAULT", "admin_email")
        email_list = config.get("DEFAULT", "email_list")

        download_speed_flag = config.get("DEFAULT", "download_speed_flag")
        if not download_speed_flag.isdigit():
            download_speed_flag = 0.15
        else:
            download_speed_flag = int(download_speed_flag) / 1000

        download_percentage_flag = config.get("DEFAULT", "download_percentage_flag")
        if not download_percentage_flag.isdigit():
            download_percentage_flag = 0.3
        else:
            if int(download_percentage_flag) > 100:
                download_percentage_flag = 0.99
            else:
                download_percentage_flag = int(download_percentage_flag) / 100

        weight_tmp = config.get("DEFAULT", "video_weight")
        weight = weight_tmp.split(",")
        if len(weight) == 3:
            if "3" not in weight or "2" not in weight or "1" not in weight:
                video_weight = [3, 2, 1]
            else:
                video_weight = [int(weight[0]), int(weight[1]), int(weight[2])]
        else:
            video_weight = [3, 2, 1]

        interval = config.get("DEFAULT", "interval")
        if not interval.isdigit():
            interval = 4
        else:
            interval = round(float(interval))
            if interval < 2:
                interval = 2
            else:
                if interval > 24:
                    interval = 24

        tmdb_key = config.get("DEFAULT", "tmdb_key")
        i = 0  # 0706
        modify_host_file()
        while True:
            i += 1
            try:
                tmdb = TMDb()
                tmdb.api_key = tmdb_key
                find_video = Find()
                res = find_video.find("tt8115900", "imdb_id")
                if res:
                    break
                else:
                    time.sleep(30)
                    modify_host_file()
            except:
                time.sleep(30)
                modify_host_file()
            if i == 2:
                break

        return 1


if __name__ == '__main__':
    flag = init_media_flow()
    if flag == 1:
        run_media()
        schedule.every(interval).hours.do(run_media)  # 0706
        while True:
            schedule.run_pending()
            time.sleep(1)
    else:
        sys.exit()
