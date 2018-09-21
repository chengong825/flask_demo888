
from info import constants
from info.models import User, News, Category
from info.utils.common import user_login_data
from info.utils.response_code import RET
from . import index_blu
from flask import render_template, current_app, session, request, jsonify, g


@index_blu.route('/')
@user_login_data
def index():
    # 获取点击排行数据
    news_list = None
    try:
        news_list = News.query.order_by(News.clicks.desc()).limit(constants.CLICK_RANK_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)
    click_news_list = []
    for news in news_list if news_list else []:
        click_news_list.append(news.to_basic_dict())
            # 获取新闻分类数据
    categories = Category.query.all()

    # 定义列表保存分类数据
    categories_dicts = []
    if categories:

        for category in categories:
            # 拼接内容

            categories_dicts.append(category.to_dict())

    data = {
        "user_info": g.user.to_dict() if g.user else None,
        "click_news_list": click_news_list,
        "categories": categories_dicts
    }
    return render_template('news/index.html', data=data)
@index_blu.route('/newslist')
def get_news_list():
    """
    获取指定分类的新闻列表
    1. 获取参数
    2. 校验参数
    3. 查询数据
    4. 返回数据
    :return:
    """
    cid=request.args.get('cid',1)
    page=request.args.get('page',1)
    per_page=request.args.get('per_page',constants.HOME_PAGE_MAX_NEWS)
    try:
        page = int(page)
        per_page = int(per_page)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
        # 3. 查询数据并分页
    filters = [News.status == 0]
    # 如果分类id不为1，那么添加分类id的过滤

    if cid != "1":
        filters.append(News.category_id == cid)
    try:
        paginate = News.query.filter(*filters).order_by(News.create_time.desc()).paginate(page, per_page, False)
        # 获取查询出来的数据
        items = paginate.items
        # 获取到总页数
        total_page = paginate.pages
        current_page = paginate.page
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据查询失败")

    # if cid!='1':
    #     try:
    #         # paginate = Category.query.get(cid).news_list.order_by(News.create_time.desc()).paginate(page, per_page, False)
    #         paginate = News.query.filter(News.category_id == cid).order_by(News.create_time.desc()).paginate(page, per_page, False)
    #         items = paginate.items
    #         # 获取到总页数
    #         total_page = paginate.pages
    #         current_page = paginate.page
    #     except Exception as e:
    #         current_app.logger.error(e)
    #         return jsonify(errno=RET.DBERR, errmsg="数据查询失败")

    news_li = []
    for news in items:
        news_li.append(news.to_basic_dict())

    # 4. 返回数据
    return jsonify(errno=RET.OK, errmsg="OK", totalPage=total_page, currentPage=current_page, newsList=news_li,
                   cid=cid)
@index_blu.route('/favicon.ico')
def favicon():
    return current_app.send_static_file('news/favicon.ico')
