# pylint: disable=global-statement,redefined-outer-name
import argparse
import csv
import glob
import json
import os
import re

import yaml
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    send_from_directory,
    send_file,
    url_for,
)
from flask_frozen import Freezer
from flaskext.markdown import Markdown

# from flaskext.cache import Cache
import pytz
from pytz import timezone
import tzlocal
import datetime
from dateutil import tz
from functools import reduce, partial
from typing import Callable, Tuple


def chain_functions(*functions: Callable) -> Callable:
    def closure(*args: Tuple) -> Tuple:
        return reduce(
            lambda acc, func: func(*acc) if isinstance(acc, tuple) else func(acc),
            functions,
            args,
        )

    return closure


site_data = {}
by_uid = {}


def paper_check(row):
    return "paper" in row["type"]


def jobs_check(row):
    return "jobs" in row["type"]


def industry_check(row):
    return "industry" in row["type"]


def music_check(row):
    return "music" in row["type"]


def lbd_check(row):
    return "lbd" in row["type"]


def group_by_days(sdata):
    groups = {}
    for row in sdata["events"]:
        groups[row["day"]] = groups.get(row["day"], []) + [row]

    def f(day, day_events):
        filterbycategory = lambda cat: list(
            filter(lambda x: x["category"] == cat, day_events)
        )
        speakers = filterbycategory("All Meeting")
        posters = filterbycategory("Poster session")
        lbd = filterbycategory("LBD")
        music = filterbycategory("Music")
        industry = filterbycategory("Industry")
        meetup = filterbycategory("Meetup")
        vmeetup = filterbycategory("VMeetup")
        master = filterbycategory("Masterclass")
        wimir = filterbycategory("WiMIR Meetup")
        special = filterbycategory("Meetup-Special")
        opening = filterbycategory("Opening")
        business = filterbycategory("Awards")
        social = filterbycategory("Social")
        tutorials = filterbycategory("Tutorials")

        out = {
            "uid": day,
            "speakers": speakers,
            "meetup": meetup,
            "special": special,
            "master": master,
            "wimir": wimir,
            "posters": posters,
            "lbd": lbd,
            "music": music,
            "industry": industry,
            "day": day,
            "opening": opening,
            "business": business,
            "social": social,
            "vmeetup": vmeetup,
            "tutorials": tutorials,
        }
        return out

    return [(day, f(day, groups[day])) for day in map(str, range(1, 6))]


def main(site_data_path):
    global site_data, by_uid
    extra_files = ["README.md"]
    # Load all for your sitedata one time.
    for f in glob.glob(site_data_path + "/*"):
        extra_files.append(f)
        name, typ = f.split("/")[-1].split(".")
        if typ == "json":
            site_data[name] = chain_functions(
                open,
                json.load,
            )(f)
        elif typ in {"csv", "tsv"}:
            site_data[name] = chain_functions(
                open,
                csv.DictReader,
                list,
            )(f)
        elif typ == "yml":
            site_data[name] = chain_functions(
                open,
                lambda x: x.read(),
                partial(yaml.load, Loader=yaml.SafeLoader),
            )(f)
    for typ in ["papers", "industry", "music", "lbds", "events", "jobs"]:
        by_uid[typ] = {}
        for p in site_data[typ]:
            by_uid[typ][p["uid"]] = p
    print("Data Successfully Loaded")
    days, events = zip(*group_by_days(site_data))
    site_data["days"] = events
    by_uid["days"] = dict(zip(days, events))

    return extra_files


# ------------- SERVER CODE -------------------->

app = Flask(__name__)
# cache = Cache(app,config={'CACHE_TYPE': 'simple'})
app.config.from_object(__name__)
freezer = Freezer(app)
markdown = Markdown(app)

# pre-load the site data for gunicorn
main(os.getenv("SITE_DATA_PATH", "sitedata/"))

# MAIN PAGES


def _data():
    data = {}
    data["config"] = site_data["config"]
    return data


@app.route("/")
def index():
    return redirect("/calendar.html")


# TOP LEVEL PAGES


@app.route("/index.html")
def home():
    return redirect("/calendar.html")


@app.route("/papers.html")
def papers():
    data = _data()
    data["papers"] = site_data["papers"]
    return render_template("papers.html", **data)


@app.route("/paper_vis.html")
def paper_vis():
    data = _data()
    return render_template("papers_vis.html", **data)


@app.route("/calendar.html")
def schedule():
    data = _data()
    data["days"] = group_by_days(site_data)
    return render_template("schedule.html", **data)


@app.route("/tutorials.html")
def tutorials():
    data = _data()
    data["tutorials"] = [t for t in site_data["events"] if t["category"] == "Tutorials"]
    return render_template("tutorials.html", **data)


@app.route("/music.html")
def musics():
    data = _data()
    data["music"] = site_data["music"]
    return render_template("music.html", **data)


@app.route("/jobs.html")
def job_board():
    data = _data()
    data["jobs"] = site_data["jobs"]
    return render_template("jobs.html", **data)


@app.route("/industry.html")
def industries():
    data = _data()
    data["industry"] = site_data["industry"]
    return render_template("industry.html", **data)


@app.route("/lbds.html")
def lbds():
    data = _data()
    data["lbds"] = site_data["lbds"]
    return render_template("lbds.html", **data)


@app.route("/lbds_vis.html")
def lbds_vis():
    data = _data()
    return render_template("lbds_vis.html", **data)


@app.route("/special_meetings.html")
def topics():
    data = _data()
    return render_template("special_meetings.html", **data)


# DOWNLOAD CALENDAR


@app.route("/getCalendar")
def get_calendar():
    filepath = "static/calendar/"
    filename = "ISMIR_2025.ics"
    return send_file(os.path.join(filepath, filename), as_attachment=True)


def extract_list_field(v, key):
    value = v.get(key, "")
    if isinstance(value, list):
        return value
    else:
        # remove starting and trailing spaces, captalize first letter of each term
        toCap = lambda s: s[:1].upper() + s[1:] if s else s
        return [
            toCap(x.strip()) for x in sum([x.split("->") for x in value.split(";")], [])
        ]


def remove_nested_parens_and_braces(s: str) -> str:
    # remove innermost (...) or {...} (and optional trailing '*') repeatedly
    while True:
        new = re.sub(r"\s*(\([^()]*\)|\{[^{}]*\})\*?", "", s)
        if new == s:
            return new
        s = new


def remove_affiliation(s):
    clean = remove_nested_parens_and_braces(s)
    # replace more than one space with single space
    clean = re.sub(r"\s+", " ", clean)
    clean = clean.replace(",", ";")
    names = [n.strip() for n in clean.split(";") if n.strip()]
    return names


def format_paper(v):
    list_keys = [
        "authors",
        "primary_subject",
        "secondary_subject",
        "session",
        "authors_and_affil",
    ]
    list_fields = {}
    for key in list_keys:
        list_fields[key] = extract_list_field(v, key)

    process = lambda s: s.replace("\n ", "\n")

    reviews = {
        k: process(v.get(k, ""))
        for k in ["review1", "review2", "review3", "meta_review", "publish_reviews"]
    }
    return {
        "id": v["uid"],
        "session": v["session"],
        "position": "{:02d}".format(int(v["position"])),
        "forum": v["uid"],
        "pic_id": v["thumbnail"],
        "content": {
            "title": v["title"],
            "paper_presentation": v["paper_presentation"],
            "long_presentation": v["long_presentation"],
            "authors": remove_affiliation(v["authors_and_affil"]),
            "authors_and_affil": list_fields["authors_and_affil"],
            "keywords": list(
                set(list_fields["primary_subject"] + list_fields["secondary_subject"])
            ),
            "abstract": v["abstract"]
            + '<br><br> <b><p align="center">[Direct link to video]({})</b>'.format(
                v["video"]
            ),
            "TLDR": v["abstract"],
            "poster_pdf": v.get("poster_pdf", ""),
            "session": list_fields["session"],
            "pdf_path": v.get("pdf_path", ""),
            "video": v["video"].replace("/open?id=", "/uc?export=preview&id="),
            "channel_url": v["channel_url"],
            "slack_channel": v["slack_channel"],
            "day": v["day"],
        },
        "poster_pdf": "GLTR_poster.pdf",
        "reviews": reviews,
    }


def format_lbd(v):
    list_keys = ["authors", "session"]
    list_fields = {}
    for key in list_keys:
        list_fields[key] = extract_list_field(v, key)
    channel_name = v.get("channel_name", "")
    channel_url = v.get("channel_url", "")
    return {
        "id": v["uid"],
        "position": v["position"],
        "forum": v["uid"],
        "content": {
            "title": v["title"],
            "authors": list_fields["authors"],
            "abstract": v["abstract"],
            "TLDR": v["abstract"],
            "session": list_fields["session"],
            "thumbnail_link": v.get("thumbnail_link", ""),
            "poster_link": v.get("poster_link", ""),
            "paper_link": v.get("paper_link", ""),
            "poster_type": v.get("poster_type", ""),
            "bilibili_id": v.get("bilibili_id", ""),
            "youtube_id": v.get("youtube_id", "").replace(
                "/file/d/", "/uc?export=preview&id="
            ),
            "channel_name": channel_name,
            "channel_url": channel_url,
            "day": 4,
        },
    }


def format_workshop(v):
    list_keys = ["authors"]
    list_fields = {}
    for key in list_keys:
        list_fields[key] = extract_list_field(v, key)

    return {
        "id": v["uid"],
        "title": v["title"],
        "organizers": list_fields["authors"],
        "abstract": v["abstract"],
    }


def format_music(v):
    return {
        "id": v["uid"],
        "content": {
            "title": v["title"],
            "authors": v["authors"],
            "affiliation": v["affiliation"],
            "abstract": v["abstract"],
            "bio": v["bio"],
            "web_link": v["web_link"],
            "session": v["session"],
            "yt_id": v["yt_id"],
            "bb_id": v["bb_id"],
        },
    }


def format_jobs(v):
    return {
        "id": v["uid"],
        "content": {
            "title": v["title"],
            "jd": v["jd"],
            "channel_name": v["channel_name"],
            "channel_url": v["channel_url"],
            "company": v["company"],
            "external_web_link": v["external_web_link"],
        },
    }


def format_industry(v):
    return {
        "id": v["uid"],
        "content": {
            "title": v["title"],
            "session": v["session"],
            "channel_name": v["channel_name"],
            "channel_url": v["channel_url"],
            "company": v["company"],
        },
    }


@app.template_filter("localcheck")
def datetimelocalcheck(s):
    return tzlocal.get_localzone()


@app.template_filter("localizetime")
def localizetime(date, time, timezone):
    to_zone = tz.gettz(str(timezone))
    date = datetime.datetime.strptime(date + " " + time, "%Y-%m-%d %H:%M")
    ref_date_tz = pytz.timezone("Asia/Kolkata").localize(
        date
    )  # [TODO] take ref time zone as input
    local_date = ref_date_tz.astimezone(to_zone)
    return local_date.strftime("%Y-%m-%d"), local_date.strftime("%H:%M")


# ITEM PAGES


@app.route("/day_<day>.html")
def day(day):
    uid = day
    v = by_uid["days"][uid]
    data = _data()
    data["day"] = v
    data["daynum"] = uid
    return render_template("day.html", **data)


@app.route("/poster_<poster>.html")
def poster(poster):
    uid = poster
    v = by_uid["papers"][uid]
    data = _data()
    data["paper"] = format_paper(v)
    return render_template("poster.html", **data)


@app.route("/speaker_<speaker>.html")
def speaker(speaker):
    uid = speaker
    v = by_uid["speakers"][uid]
    data = _data()
    data["speaker"] = v
    return render_template("speaker.html", **data)


@app.route("/workshop_<workshop>.html")
def workshop(workshop):
    uid = workshop
    v = by_uid["workshops"][uid]
    data = _data()
    data["workshop"] = format_workshop(v)
    return render_template("workshop.html", **data)


@app.route("/music_<music>.html")
def music(music):
    uid = music
    v = by_uid["music"][uid]
    data = _data()
    data["music"] = v
    return render_template("piece.html", **data)


@app.route("/jobs_<jobs>.html")
def jobs(jobs):
    uid = jobs
    v = by_uid["jobs"][uid]
    data = _data()
    data["jobs"] = v
    return render_template("jobs_template.html", **data)


@app.route("/industry_<industry>.html")
def industry(industry):
    uid = industry
    v = by_uid["industry"][uid]
    data = _data()
    data["industry"] = v
    return render_template("company.html", **data)


@app.route("/lbd_<lbd>.html")
def lbd(lbd):
    uid = lbd
    v = by_uid["lbds"][uid]
    data = _data()
    data["lbd"] = format_lbd(v)
    return render_template("lbd.html", **data)


@app.route("/chat.html")
def chat():
    data = _data()
    return render_template("chat.html", **data)


# FRONT END SERVING


@app.route("/papers.json")
def paper_json():
    json = []
    for v in site_data["papers"]:
        json.append(format_paper(v))
    return jsonify(json)


@app.route("/music.json")
def music_json():
    json = []
    for v in site_data["music"]:
        json.append(v)
    return jsonify(json)


@app.route("/jobs.json")
def jobs_json():
    json = []
    for v in site_data["jobs"]:
        json.append(v)
    return jsonify(json)


@app.route("/industry.json")
def industry_json():
    json = []
    for v in site_data["industry"]:
        json.append(v)
    return jsonify(json)


@app.route("/lbds.json")
def lbds_json():
    json = []
    for v in site_data["lbds"]:
        json.append(format_lbd(v))
    return jsonify(json)


@app.route("/static/<path:path>")
def send_static(path):
    if "wo_num" not in path:
        return send_from_directory("static", path)


@app.route("/serve_<path>.json")
def serve(path):
    return jsonify(site_data[path])


# --------------- DRIVER CODE -------------------------->
# Code to turn it all static


@freezer.register_generator
def generator():

    for paper in site_data["papers"]:
        yield "poster", {"poster": str(paper["uid"])}
    for music in site_data["music"]:
        yield "music", {"music": str(music["uid"])}
    for industry in site_data["industry"]:
        yield "industry", {"industry": str(industry["uid"])}
    for jobs in site_data["jobs"]:
        yield "jobs", {"jobs": str(jobs["uid"])}
    for lbd in site_data["lbds"]:
        yield "lbd", {"lbd": str(lbd["uid"])}
    for day in site_data["days"]:
        yield "day", {"day": str(day["uid"])}

    for key in site_data:
        if key != "days":
            yield "serve", {"path": key}


def parse_arguments():
    parser = argparse.ArgumentParser(description="MiniConf Portal Command Line")

    parser.add_argument(
        "--build",
        action="store_true",
        default=False,
        help="Convert the site to static assets",
    )

    parser.add_argument(
        "-b",
        action="store_true",
        default=False,
        dest="build",
        help="Convert the site to static assets",
    )

    parser.add_argument(
        "--path", help="Pass the JSON data path and run the server", required=True
    )

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_arguments()
    data_path = args.path

    if data_path is None:
        raise Exception("--path for the root directory for data is missing")

    extra_files = main(data_path)
    if args.build:
        freezer.freeze()
    else:
        debug_val = False
        if os.getenv("FLASK_DEBUG") == "True":
            debug_val = True
        app.run(host="0.0.0.0", port=10000, debug=debug_val, extra_files=extra_files)
