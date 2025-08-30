# !/bin/bash
# Download the latest industry data from Google Sheets and save it as a CSV file
wget "https://docs.google.com/spreadsheets/d/1uPqEdBR_0BARSdDQVyZ9h6lG8k50xoLAFFu6sW-qnNQ/export?format=csv&gid=1530113561" -O sitedata/industry.csv
wget "https://docs.google.com/spreadsheets/d/1uPqEdBR_0BARSdDQVyZ9h6lG8k50xoLAFFu6sW-qnNQ/export?format=csv&gid=1117978644" -O sitedata/papers.csv 
wget "https://docs.google.com/spreadsheets/d/1uPqEdBR_0BARSdDQVyZ9h6lG8k50xoLAFFu6sW-qnNQ/export?format=csv&gid=1380524613" -O sitedata/events.csv
wget "https://docs.google.com/spreadsheets/d/1uPqEdBR_0BARSdDQVyZ9h6lG8k50xoLAFFu6sW-qnNQ/export?format=csv&gid=1229247899" -O sitedata/music.csv

# Get thumbnail images from google drive urls
python scripts/get_thumbnails.py