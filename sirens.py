#!/usr/bin/env python3
import os
import datetime
import xml.etree.ElementTree as ET
import urllib.parse
import json
import socket

from flask import Flask, Response, send_from_directory
from mutagen.mp3 import MP3
from werkzeug.utils import secure_filename


app = Flask(__name__)


def get_local_ip():
    try:
        # Cria um socket UDP e se conecta a um endereço externo, sem enviar dados
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # Usa um servidor DNS do Google apenas para determinar a interface de rede correta
            local_ip = s.getsockname()[0]

        return f"http://{local_ip}:5000"
    except Exception as e:
        return f"Error on getting IP adress: {e}"


AUDIO_FOLDER = 'episodes'
COVER_FOLDER = 'covers'
BASE_URL = get_local_ip() #'http://192.168.68.103:5000'


PODCAST_CONFIG = {
    'title': 'Manducast',
    'link': f'{BASE_URL}/feed',
    'description': 'Audio e audiobooks',
    'language': 'pt-br',
    'author': 'Henrique Manduca',
    'email': 'seu.email@exemplo.com',
    'image': f'{BASE_URL}/covers/default.png',
    'explicit': 'false',
    'categories': ['Education']
}


# Certifique-se de que as pastas existam
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(COVER_FOLDER, exist_ok=True)


@app.route('/feed')
def get_feed():
    # Criar manualmente o XML conforme especificações iTunes
    rss = ET.Element('rss')
    rss.set('version', '2.0')
    rss.set('xmlns:itunes', 'http://www.itunes.com/dtds/podcast-1.0.dtd')
    rss.set('xmlns:content', 'http://purl.org/rss/1.0/modules/content/')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')

    channel = ET.SubElement(rss, 'channel')

    ET.SubElement(channel, 'title').text = PODCAST_CONFIG['title']
    ET.SubElement(channel, 'link').text = PODCAST_CONFIG['link']
    ET.SubElement(channel, 'description').text = PODCAST_CONFIG['description']
    ET.SubElement(channel, 'language').text = PODCAST_CONFIG['language']

    # Elementos específicos do iTunes
    ET.SubElement(channel, 'itunes:author').text = PODCAST_CONFIG['author']
    ET.SubElement(channel, 'itunes:explicit').text = PODCAST_CONFIG['explicit']

    # Elemento de imagem para iTunes
    itunes_image = ET.SubElement(channel, 'itunes:image')
    itunes_image.set('href', PODCAST_CONFIG['image'])

    # Elemento de imagem para RSS padrão
    image = ET.SubElement(channel, 'image')
    ET.SubElement(image, 'url').text = PODCAST_CONFIG['image']
    ET.SubElement(image, 'title').text = PODCAST_CONFIG['title']
    ET.SubElement(image, 'link').text = PODCAST_CONFIG['link']

    owner = ET.SubElement(channel, 'itunes:owner')
    ET.SubElement(owner, 'itunes:name').text = PODCAST_CONFIG['author']
    ET.SubElement(owner, 'itunes:email').text = PODCAST_CONFIG['email']

    # Categorias para iTunes
    for category in PODCAST_CONFIG['categories']:
        itunes_category = ET.SubElement(channel, 'itunes:category')
        itunes_category.set('text', category)

    # Link atom para conformidade com feed validators
    atom_link = ET.SubElement(channel, 'atom:link')
    atom_link.set('href', PODCAST_CONFIG['link'])
    atom_link.set('rel', 'self')
    atom_link.set('type', 'application/rss+xml')

    with open('database.json', 'r', encoding='utf-8') as arquivo:
        database = json.load(arquivo)

    for filename in sorted(os.listdir(AUDIO_FOLDER), reverse=True):
        if filename.endswith('.mp3'):
            file_path = os.path.join(AUDIO_FOLDER, filename)
            try:
                audio = MP3(file_path)
                duration = int(audio.info.length)
                duration_str = f"{duration // 3600:02d}:{(duration % 3600) // 60:02d}:{duration % 60:02d}"
            except Exception:
                duration_str = '00:00:00'

            print(os.path.splitext(filename)[0])
            title = database[os.path.splitext(filename)[0]]['name']

            pub_date = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            pub_date_str = pub_date.strftime('%a, %d %b %Y %H:%M:%S -0300')
            file_size = os.path.getsize(file_path)

            episode_url = f"{BASE_URL}/episodes/{urllib.parse.quote(filename)}"

            item = ET.SubElement(channel, 'item')
            ET.SubElement(item, 'title').text = title
            ET.SubElement(item, 'link').text = episode_url
            ET.SubElement(item, 'guid', isPermaLink="false").text = episode_url
            ET.SubElement(item, 'description').text = f"Episódio: {title}"
            ET.SubElement(item, 'pubDate').text = pub_date_str

            # Enclosure - esta é a parte crucial para apps de podcast
            enclosure = ET.SubElement(item, 'enclosure')
            enclosure.set('url', episode_url)
            enclosure.set('type', 'audio/mpeg')
            enclosure.set('length', str(file_size))

            ET.SubElement(item, 'itunes:title').text = title
            ET.SubElement(item, 'itunes:author').text = PODCAST_CONFIG['author']
            ET.SubElement(item, 'itunes:duration').text = duration_str
            ET.SubElement(item, 'itunes:explicit').text = PODCAST_CONFIG['explicit']

            # Opcional: Adiciona imagem específica para o episódio
            episode_image = ET.SubElement(item, 'itunes:image')
            cover_name = urllib.parse.quote(filename).replace("mp3", "jpg")
            episode_image.set('href', f"{BASE_URL}/covers/{cover_name}")

    xml_str = '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(rss, encoding='unicode')
    return Response(xml_str, mimetype='application/rss+xml; charset=utf-8')


@app.route('/episodes/<filename>')
def get_episode(filename):
    return send_from_directory(AUDIO_FOLDER, secure_filename(filename))


@app.route('/covers/<filename>')
def get_cover(filename):
    return send_from_directory(COVER_FOLDER, secure_filename(filename))


@app.route('/')
def home():
    return """
    <html>
        <head><title>Servidor de Podcast</title></head>
        <body>
            <h1>Servidor de Podcast</h1>
            <p>O feed RSS está disponível em <a href="/feed">/feed</a></p>
        </body>
    </html>
    """


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
