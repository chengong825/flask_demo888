import logging
from logging.handlers import RotatingFileHandler

import redis
from flask import Flask, g, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_session import Session
from config import config


# 数据库

db = SQLAlchemy()
redis_store = None

from info.utils.common import do_index_class, user_login_data


def create_app(config_name):
    """通过传入不同的配置名字，初始化其对应配置的应用实例"""
    setup_log(config_name)

    app = Flask(__name__)

    # 配置
    app.config.from_object(config[config_name])
    # 配置数据库
    db.init_app(app)
    # 配置redis
    global redis_store
    redis_store = redis.StrictRedis(host=config[config_name].REDIS_HOST, port=config[config_name].REDIS_PORT)
    # 开启csrf保护
    CSRFProtect(app)
    # 设置session保存位置
    @app.after_request
    def do_after_request(resp):
        # 调用函数生成 csrf_token
        csrf_token = generate_csrf()
        # 通过 cookie 将值传给前端
        resp.set_cookie("csrf_token", csrf_token)
        return  resp

    Session(app)
    # 注册蓝图
    app.add_template_filter(do_index_class,"index_class")
    from info.modules.index import index_blu
    app.register_blueprint(index_blu)
    from info.modules.passport import passport_blu
    app.register_blueprint(passport_blu)
    from info.modules.news import news_blu
    app.register_blueprint(news_blu)
    from info.modules.profile import profile_blu
    app.register_blueprint(profile_blu)
    from info.modules.admin import admin_blu
    app.register_blueprint(admin_blu)
    @app.errorhandler(404)
    @user_login_data
    def page_not_found(_):
        user = g.user
        data = {"user_info": user.to_dict() if user else None}
        return render_template('news/404.html', data=data)

    return app
def setup_log(config_name):
    """配置日志"""

    # 设置日志的记录等级
    logging.basicConfig(level=config[config_name].LOG_LEVEL)  # 调试debug级
    # 创建日志记录器，指明日志保存的路径、每个日志文件的最大大小、保存的日志文件个数上限
    file_log_handler = RotatingFileHandler("logs/log", maxBytes=1024 * 1024 * 100, backupCount=10)
    # 创建日志记录的格式 日志等级 输入日志信息的文件名 行数 日志信息
    formatter = logging.Formatter('%(levelname)s %(filename)s:%(lineno)d %(message)s')
    # 为刚创建的日志记录器设置日志记录格式
    file_log_handler.setFormatter(formatter)
    # 为全局的日志工具对象（flask app使用的）添加日志记录器
    logging.getLogger().addHandler(file_log_handler)