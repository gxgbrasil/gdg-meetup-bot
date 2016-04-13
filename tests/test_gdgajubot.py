# -*- coding: utf-8 -*-
import sys

sys.path.append('../')

import unittest
import os
from datetime import datetime

from gdgajubot import gdgajubot
from gdgajubot.util import AJU_TZ


class MetaCall:
    def __call__(self, item, *args, **kwargs):
        return item, args, kwargs

    def __getattr__(self, item):
        def _call(*args, **kwargs):
            return self(item, *args, **kwargs)
        return _call

# Usado nos testes para identificar o método chamado (nome e argumentos)
CALL = MetaCall()


class MockTeleBot:
    calls = []

    # Registra cada método chamado da classe
    def __getattr__(self, item):
        def _call(*args, **kwargs):
            self.calls.append(CALL(item, *args, **kwargs))
        return _call


class MockMessage:
    def __init__(self, **kwargs):
        self.__dict__.update(**kwargs)

    # Método definido para não ter AttributeError
    def __getattr__(self, item):
        return self


class MockResources:
    # Falso cache de eventos
    cache_events = [
        {'link': 'http://www.meetup.com/GDG-Aracaju/events/229313880/',
         'name': 'Hackeando sua Carreira #Hangout',
         'time': 1459378800000},
        {'link': 'http://www.meetup.com/GDG-Aracaju/events/229623381/',
         'name': 'Android Jam 2: Talks Dia 2',
         'time': 1459612800000},
        {'link': 'http://www.meetup.com/GDG-Aracaju/events/mwnsrlyvgbjb/',
         'name': 'Coding Dojo',
         'time': 1459980000000},
        {'link': 'http://www.meetup.com/GDG-Aracaju/events/229591464/',
         'name': 'O Caminho para uma Arquitetura Elegante #Hangout',
         'time': 1460160000000},
        {'link': 'http://www.meetup.com/GDG-Aracaju/events/229770309/',
         'name': 'Android Jam 2: #Curso Dia 2',
         'time': 1460217600000},
        {'link': 'http://www.meetup.com/GDG-Aracaju/events/mwnsrlyvhbgb/',
         'name': 'Coding Dojo',
         'time': 1462399200000},
        {'link': 'http://www.meetup.com/GDG-Aracaju/events/229951204/',
         'name': 'Google I/O Extended',
         'time': 1463587200000},
        {'link': 'http://www.meetup.com/GDG-Aracaju/events/229951264/',
         'name': 'Google IO Extended 2016',
         'time': 1463608800000},
    ]

    def get_events(self, n):
        return self.cache_events[:n]

    # Valores fixos para get_packt_free_book
    bookname = "Android 2099"
    bookts = 4091565600

    def get_packt_free_book(self):
        return self.bookname, self.bookts


class TestGDGAjuBot(unittest.TestCase):
    config = {'group_name': 'Test-Bot'}

    # Regular expressions tests

    def test_find_ruby(self):
        assert gdgajubot.find_ruby("Olá ruby GDG")
        assert gdgajubot.find_ruby("Olá RUBY GDG")
        assert gdgajubot.find_ruby("Olá Ruby GDG")
        assert not gdgajubot.find_ruby("OlárubyGDG")

    def test_find_java(self):
        assert gdgajubot.find_java("Olá java GDG")
        assert gdgajubot.find_java("Olá Java GDG")
        assert gdgajubot.find_java("Olá JAVA GDG")
        assert not gdgajubot.find_java("OlájavaGDG")

    def test_find_python(self):
        assert gdgajubot.find_python("Olá python GDG")
        assert gdgajubot.find_python("Olá Python GDG")
        assert gdgajubot.find_python("Olá PYTHON GDG")
        assert not gdgajubot.find_python("OlápythonGDG")

    # Bot commands tests

    def test_send_welcome(self):
        bot, resources, message = MockTeleBot(), MockResources(), MockMessage()
        g_bot = gdgajubot.GDGAjuBot(bot, resources, self.config)
        g_bot.send_welcome(message)
        self._assert_send_welcome(bot.calls[-1], message)

    def test_list_upcoming_events(self):
        bot, resources, message = MockTeleBot(), MockResources(), MockMessage()
        g_bot = gdgajubot.GDGAjuBot(bot, resources, self.config)
        g_bot.list_upcoming_events(message)

        # Verifica se o response criado está correto
        self._assert_list_upcoming_events(bot.calls[-1], message)

        # Garante que o cache mutável não gerará uma exceção
        n_calls = len(bot.calls)
        g_bot.list_upcoming_events(message)
        self.assertGreater(len(bot.calls), n_calls)

    def test_packtpub_free_learning(self):
        bot, resources, message = MockTeleBot(), MockResources(), MockMessage()
        g_bot = gdgajubot.GDGAjuBot(bot, resources, self.config)
        ts = resources.bookts

        # Sem warning
        g_bot.packtpub_free_learning(message, now=datetime.fromtimestamp(ts - 10*3600, tz=AJU_TZ))
        self._assert_packtpub_free_learning(bot.calls[-1], message)

        # Os próximos testes verificam cada um dos warnings
        g_bot.packtpub_free_learning(message, now=datetime.fromtimestamp(ts - 59*60, tz=AJU_TZ))
        self._assert_packtpub_free_learning(bot.calls[-1], message, warning="\n\nFaltam menos de 1 hora!")

        g_bot.packtpub_free_learning(message, now=datetime.fromtimestamp(ts - 29*60, tz=AJU_TZ))
        self._assert_packtpub_free_learning(bot.calls[-1], message, warning="\n\nFaltam menos de meia hora!")

        g_bot.packtpub_free_learning(message, now=datetime.fromtimestamp(ts - 9*60, tz=AJU_TZ))
        self._assert_packtpub_free_learning(bot.calls[-1], message, warning="\n\nFaltam menos de 10 minutos!")

        g_bot.packtpub_free_learning(message, now=datetime.fromtimestamp(ts - 59, tz=AJU_TZ))
        self._assert_packtpub_free_learning(bot.calls[-1], message, warning="\n\nFaltam menos de 1 minuto!")

        g_bot.packtpub_free_learning(message, now=datetime.fromtimestamp(ts - 29, tz=AJU_TZ))
        self._assert_packtpub_free_learning(bot.calls[-1], message, warning="\n\nFaltam menos de 30 segundos!")

    def test_changelog(self):
        bot, resources, message = MockTeleBot(), MockResources(), MockMessage(id=0xB00B)
        g_bot = gdgajubot.GDGAjuBot(bot, resources, self.config)
        g_bot.changelog(message)
        self._assert_changelog(bot.calls[-1], message)

    def _assert_send_welcome(self, called, message):
        self.assertEqual(called,
                         CALL.reply_to(message, "Este bot faz buscas no Meetup do Test-Bot"))

    def _assert_list_upcoming_events(self, called, message):
        r = ("[Hackeando sua Carreira #Hangout](http://www.meetup.com/GDG-Aracaju/events/229313880/): 30/03 20:00\n"
             "[Android Jam 2: Talks Dia 2](http://www.meetup.com/GDG-Aracaju/events/229623381/): 02/04 13:00\n"
             "[Coding Dojo](http://www.meetup.com/GDG-Aracaju/events/mwnsrlyvgbjb/): 06/04 19:00\n"
             "[O Caminho para uma Arquitetura Elegante #Hangout](http://www.meetup.com/GDG-Aracaju/events/229591464/): 08/04 21:00\n"
             "[Android Jam 2: #Curso Dia 2](http://www.meetup.com/GDG-Aracaju/events/229770309/): 09/04 13:00")
        self.assertEqual(called,
                         CALL.reply_to(message, r, parse_mode="Markdown", disable_web_page_preview=True))

    def _assert_packtpub_free_learning(self, called, message, warning=''):
        r = "O livro de hoje é: [Android 2099](https://www.packtpub.com/packt/offers/free-learning)" + warning
        self.assertEqual(called,
                         CALL.reply_to(message, r, parse_mode="Markdown", disable_web_page_preview=True))

    def _assert_changelog(self, called, message):
        r = "https://github.com/GDGAracaju/GDGAjuBot/blob/master/CHANGELOG.md"
        self.assertEqual(called, CALL.send_message(message.chat.id, r))

    # Internals tests

    def test_smart_reply(self):
        bot, resources = MockTeleBot(), MockResources()
        message = MockMessage(id=0x6D6)
        g_bot = gdgajubot.GDGAjuBot(bot, resources, self.config)
        text = "I <3 GDG Aracaju"

        # Mensagens privadas não fazem link
        message.chat.type = "private"
        g_bot._smart_reply(message, text)
        self.assertEqual(bot.calls[-1], CALL.reply_to(message, text))
        g_bot._smart_reply(message, text)
        self.assertEqual(bot.calls[-1], CALL.reply_to(message, text))

        # Alterando MockTeleBot reply_to para retornar um MockMessage com um message_id
        def _reply_to(*args):
            bot.__getattr__('reply_to')(*args)  # mantém o registro de chamada
            return MockMessage(message_id=82)
        bot.reply_to = _reply_to

        # Mensagens de grupo fazem link
        message.chat.type = "group"
        g_bot._smart_reply(message, text)
        self.assertEqual(bot.calls[-1], CALL.reply_to(message, text))
        g_bot._smart_reply(message, text)
        self.assertEqual(bot.calls[-1], CALL.send_message(message.chat.id, "Clique para ver a última resposta",
                                                          reply_to_message_id=82))

    # Routing test

    def test_handle_messages(self):
        bot, resources = MockTeleBot(), MockResources()
        g_bot = gdgajubot.GDGAjuBot(bot, resources, self.config)

        # test simple commands text
        commands_asserts = {
            '/events': self._assert_list_upcoming_events,
            '/start': self._assert_send_welcome,
            '/changelog': self._assert_changelog,
            '/book': self._assert_packtpub_free_learning,
            '/help': self._assert_send_welcome,
        }
        messages = [MockMessage(id=i, text=cmd, content_type="text")
                    for i, cmd in enumerate(commands_asserts)]
        for i, _assert in enumerate(commands_asserts.values()):
            g_bot.handle_messages(messages[i:i+1])
            _assert(bot.calls[-1], messages[i])

        # test qualifying commands text
        commands_asserts = {
            '/events@gdgajubot': self._assert_list_upcoming_events,
            '/start@erickbot': self._assert_send_welcome,
            '/changelog@wagnerbot': self._assert_changelog,
            '/book@brandinibot': self._assert_packtpub_free_learning,
            '/help@thalesbot': self._assert_send_welcome,
        }
        messages = [MockMessage(id=i, text=cmd, content_type="text")
                    for i, cmd in enumerate(commands_asserts)]
        for i, _assert in enumerate(commands_asserts.values()):
            g_bot.handle_messages(messages[i:i+1])
            _assert(bot.calls[-1], messages[i])


class TestResources(unittest.TestCase):
    cd = os.path.dirname(__file__)

    def test_extract_packt_free_book(self):
        content = open(os.path.join(self.cd, 'packtpub-free-learning.html'), 'rb')
        self.assertEqual(gdgajubot.Resources.extract_packt_free_book(content),
                         ("Oracle Enterprise Manager 12c Administration Cookbook", 1459378800))
