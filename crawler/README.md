python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
crawl4ai-setup

cd ..
PYTHONPATH=. python crawler/deep_crawler.py


WARNING: because of https://github.com/agno-agi/agno/pull/3381, we need to modify the code in agno/embeddings/sentence_transformer.py until the PR is merged