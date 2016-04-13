# encoding:utf-8
from os import environ as env
from subprocess import call
from flask import Flask, render_template, redirect, url_for, request
import tailer

DEBUG = env.get("DEBUG", "True")
RESTART_TOKEN = env.get("RESTART_TOKEN","12345")
BOT_LOGFILE = env.get("BOT_LOGFILE", 'bot.log')

def supervisorctl(command):
   return call(['supervisorctl', command]) 

def git_pull():
   return call(['git', 'pull', 'origin', 'master']) 

def tail_log_file():
    try:
        return tailer.tail(open(BOT_LOGFILE), 10)
    except FileNotFoundError:
        return ["Arquivo de log não encontrado"]

app = Flask(__name__)

@app.route('/')
def index():
    message = request.args.get('message', '')
    color = request.args.get('color', 'blue lighten-2')
    log = tail_log_file()
    return render_template('index.html', message=message, color=color, log=log)

@app.route('/restart_bot/', methods=['POST'])
def restart_bot():
    if request.form['token'] == RESTART_TOKEN:
        try:
            result = supervisorctl('restart gdgajubot')
            if result == 0:
                return redirect(url_for('index', message='Bot reiniciado'))
        except Exception as e:
            pass
    return redirect(url_for('index', message='Algo deu errado', color='red'))

@app.route('/update_deploy_bot/', methods=['POST'])
def update_deploy_bot():
    if request.form['token'] == RESTART_TOKEN:
        try:
            result_git = git_pull()
            result_restart = supervisorctl('reload')
            if result_git == 0 and result_restart == 0:
                return redirect(url_for('index', message='Bot atualizado'))
        except Exception as e:
            pass
    return redirect(url_for('index', message='Algo deu errado', color='red'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=(DEBUG=="True"))
