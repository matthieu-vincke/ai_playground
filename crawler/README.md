python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
crawl4ai-setup

cd ..
PYTHONPATH=. python crawler/deep_crawler.py