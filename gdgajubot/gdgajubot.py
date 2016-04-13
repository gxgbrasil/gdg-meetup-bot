#!/usr/bin/env python3
"""Bot do GDG-Aracaju."""
import argparse
import logging
import re
import os
import datetime

import requests
import telebot
from beaker.cache import CacheManager
from beaker.util import parse_cache_config_options
from bs4 import BeautifulSoup

from . import util

book_re = re.compile(
    r'(?s)'  # re.DOTALL
    r'"deal-of-the-day".*?'             # #deal-of-the-day
    r'<div[ >].*?<div[ >].*?'           # div div
    r'<div[ >].*?</div>.*?<div[ >].*?'  # div:nth-of-type(2)
    r'<span class="packt-js-countdown" data-countdown-to="([0-9]+)"></span>.*?'  # span.packt-js-countdown
    r'<h2[ >]\s*(.*?)\s*</h2>'          # h2
)


class Resources:
    # Configuring cache
    cache = CacheManager(**parse_cache_config_options({'cache.type': 'memory'}))

    def __init__(self, config):
        self.config = config

    @cache.cache('get_events', expire=600)
    def get_events(self, list_size=5):
        return list(self.generate_events(list_size))

    def generate_events(self, n):
        """Obtém eventos do Meetup."""
        # api v3 base url
        url = "https://api.meetup.com/%(group_name)s/events" % self.config

        # response for the events
        r = requests.get(url, params={
            'key': self.config['meetup_key'],
            'status': 'upcoming',
            'only': 'name,time,link',  # filter response to these fields
            'page': n,                 # limit to n events
        })

        return r.json()

    @cache.cache('get_packt_free_book', expire=600)
    def get_packt_free_book(self):
        r = requests.get("https://www.packtpub.com/packt/offers/free-learning")
        return self.extract_packt_free_book(r.content, r.encoding)

    @staticmethod
    def extract_packt_free_book(content, encoding='utf-8'):
        if hasattr(content, 'read'):    # file-type
            content = content.read()
        if isinstance(content, bytes):  # convert to str
            content = content.decode(encoding)

        # Try to get book with re
        try:
            m = book_re.search(content)
            book = m.group(2)
            expires = m.group(1)
            return book, int(expires)
        except Exception as e:
            logging.exception(e)

        # Fallback to html parser
        page = BeautifulSoup(content, 'html.parser')
        dealoftheday = page.select_one('#deal-of-the-day')
        book = dealoftheday.select_one('div div div:nth-of-type(2) div:nth-of-type(2) h2')
        expires = dealoftheday.select_one('span.packt-js-countdown').attrs['data-countdown-to']
        return book.text.strip(), int(expires)


# Funções de busca usadas nas easter eggs
find_ruby = re.compile(r"(?i)\bRUBY\b").search
find_java = re.compile(r"(?i)\bJAVA\b").search
find_python = re.compile(r"(?i)\bPYTHON\b").search

# Helper para definir os comandos do bot
handler = util.HandlerHelper()
commands = handler.commands


class GDGAjuBot:
    def __init__(self, bot, resources, config):
        self.bot = bot
        self.resources = resources
        self.config = config
        bot.set_update_listener(self.handle_messages)

    @commands('/start', '/help')
    def send_welcome(self, message):
        """Mensagem de apresentação do bot."""
        logging.info("/start")
        self.bot.reply_to(message, "Este bot faz buscas no Meetup do %s" % (self.config["group_name"]))

    @commands('/events')
    def list_upcoming_events(self, message):
        """Retorna a lista de eventos do Meetup."""
        logging.info("%s: %s" % (message.from_user.username, "/events"))
        try:
            next_events = self.resources.get_events(5)
            response = self._format_events(next_events)
            self._smart_reply(message, response,
                              parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            logging.exception(e)

    def _format_events(self, events):
        response = []
        for event in events:
            # If the events wasn't in cache, event['time'] is a timestamp.
            # So we format it!
            if isinstance(event['time'], int):
                # convert time returned by Meetup API
                event_dt = datetime.datetime.fromtimestamp(event['time'] / 1000, tz=util.AJU_TZ)

                # create a pretty-looking date
                event['time'] = event_dt.strftime('%d/%m %H:%M')

            response.append("[%(name)s](%(link)s): %(time)s" % event)
        return '\n'.join(response)

    @commands('/book')
    def packtpub_free_learning(self, message, now=None):
        """Retorna o livro disponível no free-learning da editora PacktPub."""
        logging.info("%s: %s" % (message.from_user.username, "/book"))
        book, expires = self.resources.get_packt_free_book()
        self._smart_reply(message, self._book_response(book, expires, now),
                          parse_mode="Markdown", disable_web_page_preview=True)

    timeleft = ((30, '30 segundos'),
                (60, '1 minuto'),
                (600, '10 minutos'),
                (1800, 'meia hora'),
                (3600, '1 hora'))

    def _book_response(self, book, expires, now=None):
        if now is None:
            now = datetime.datetime.now(tz=util.AJU_TZ)

        delta = datetime.datetime.fromtimestamp(expires, tz=util.AJU_TZ) - now
        seconds = delta.total_seconds()

        response = "O livro de hoje é: [%s](https://www.packtpub.com/packt/offers/free-learning)" % book
        for num, in_words in self.timeleft:
            if seconds <= num:
                warning = "\n\nFaltam menos de %s!" % in_words
                return response + warning
        return response

    def _smart_reply(self, message, text, **kwargs):
        # On groups or supergroups, check if I have a recent previous response to refer
        if message.chat.type in ["group", "supergroup"]:
            # Retrieve from cache and set if necessary
            key = "p%s" % util.extract_command(text)
            previous_cache = Resources.cache.get_cache(key, expire=600)
            previous = previous_cache.get(key=message.chat.id, createfunc=dict)

            # Verify if previous response is the same to send a contextual response
            if previous.get('text') == text:
                self.bot.send_message(message.chat.id, "Clique para ver a última resposta",
                                      reply_to_message_id=previous['message_id'])
            # or, send new response and update the cache
            else:
                sent = self.bot.reply_to(message, text, **kwargs)
                previous.update({'text': text, 'message_id': sent.message_id})
                previous_cache[message.chat.id] = previous  # reset expire time

        # On private chats or channels, send the normal reply...
        else:
            self.bot.reply_to(message, text, **kwargs)

    @commands('/changelog')
    def changelog(self, message):
        logging.info("%s: %s" % (message.from_user.username, "/changelog"))
        self.bot.send_message(message.chat.id, "https://github.com/GDGAracaju/GDGAjuBot/blob/master/CHANGELOG.md")

    def love_ruby(self, message):
        """Easter Egg com o Ruby."""
        logging.info("%s: %s" % (message.from_user.username, "ruby"))
        username = message.from_user.username
        self.bot.send_message(message.chat.id, username + " ama Ruby <3")

    def memory_java(self, message):
        """Easter Egg com o Java."""
        logging.info("%s: %s" % (message.from_user.username, "java"))
        self.bot.send_message(message.chat.id, "Ihh... acabou a RAM")

    def easter_python(self, message):
        """Easter Egg com o Python."""
        logging.info("%s: %s" % (message.from_user.username, "python"))
        self.bot.send_message(message.chat.id, "import antigravity")

    def handle_messages(self, messages):
        for message in messages:
            if message.content_type == "text":
                # Identifica o comando e despacha para a função correta
                command = util.extract_command(message.text)
                if command:
                    handler.handle_command(command, *(self, message))

                # Easter eggs
                elif find_ruby(message.text):
                    self.love_ruby(message)
                elif find_java(message.text):
                    self.memory_java(message)
                elif find_python(message.text):
                    self.easter_python(message)

    def start(self):
        self.bot.polling(none_stop=True, interval=0, timeout=20)


def main():
    # Configuring log
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p'
    )

    # Configuring bot parameters
    logging.info("Configurando parâmetros")
    parser = argparse.ArgumentParser(description='Bot do GDG Aracaju')
    parser.add_argument('-t', '--telegram_token', help='Token da API do Telegram', required=True)
    parser.add_argument('-m', '--meetup_key', help='Key da API do Meetup', required=True)
    parser.add_argument('-g', '--group_name', help='Grupo do Meetup', required=True)
    parser.add_argument('-d', '--dev', help='Indicador de Debug/Dev mode', action='store_true')
    parser.add_argument('--no-dev', help=argparse.SUPPRESS, dest='dev', action='store_false')

    # Get required arguments to check after parsed
    required_actions = []
    for action in parser._actions:
        if action.required:
            required_actions.append(action)
            action.required = False

    # Parse command line args
    namespace = parser.parse_args()

    # Mounting config
    _config = {k: v or os.environ.get(k.upper(), '')
               for k, v in vars(namespace).items()}

    # Verifying required arguments
    missing_args = [argparse._get_action_name(a) for a in required_actions if not _config[a.dest]]
    if missing_args:
        parser.error("missing arguments: " + ", ".join(missing_args))

    # Starting bot
    logging.info("Iniciando bot")
    if _config["dev"]:
        logging.info("Dev mode activated.")
        logging.info("Usando telegram_token=%s" % (_config["telegram_token"]))
        logging.info("Usando meetup_key=%s" % (_config["meetup_key"]))
    bot = telebot.TeleBot(_config['telegram_token'])
    resources = Resources(_config)
    gdgbot = GDGAjuBot(bot, resources, _config)
    gdgbot.start()


if __name__ == "__main__":
    main()
