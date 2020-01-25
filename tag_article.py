from google.cloud import language
from google.cloud import vision
from google.cloud import storage
from google.cloud.language import enums
from google.cloud.language import types
from google.cloud import bigquery
import os

def _get_tags(text, confidence_thresh=0.69):
    # Instantiates a client
    client = language.LanguageServiceClient()

    document = types.Document(
        content=text,
        type=enums.Document.Type.PLAIN_TEXT)
    try:
        res = client.classify_text(document)
    except Exception as err:
        print(err)
        return []
    return [tag.name for tag in res.categories]

def _insert_tags_bigquery(filename, tags):
    client = bigquery.Client()
    table_id = os.environ["ARTICLE_TAGS_TABLE"]
    table = client.get_table(table_id)
    rows =[{"filename" : filename, "tag": tags}]
    errors = client.insert_rows(table, rows)
    if errors:
        print("Got errors " + str(errors))

def _extract_text(bucket_name, filename):
    uri = f"gs://{bucket_name}/{filename}"
    client = vision.ImageAnnotatorClient()
    res = client.document_text_detection({'source': {'image_uri': uri}})
    text = res.full_text_annotation.text
    if not text:
        print("OCR error " + str(res))
    return text

def handle_article(data, context):
    bucket = data["bucket"]
    name = data["name"]
    filename, ext = os.path.splitext(name)
    text = None
    if ext in ['.tif', '.tiff', '.png', '.jpeg', '.jpg']:
        print("Extracting text from image file")
        text = _extract_text(bucket, name)
        if not text:
            print("Couldn't extract text from gs://%s/%s" % (bucket, name))
    elif ext in ['.txt']:
        print("Downloading text file from cloud")
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket)
        blob = bucket.blob(name)
        text = blob.download_as_string()
    if text:
        tags = _get_tags(text)
        print("Found %d tags for article %s" % (len(tags), name))
        _insert_tags_bigquery(name, tags)