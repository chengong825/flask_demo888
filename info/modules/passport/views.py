import re
import random

from datetime import datetime
from flask import request, abort, current_app, make_response, jsonify, session

from info import redis_store, constants, db
from info.libs.yuntongxun.sms import CCP
from info.models import User
from info.utils.captcha.captcha import captcha
from info.utils.response_code import RET
from . import passport_blu
@passport_blu.route('/image_code')
def get_image_code():
    code_id=request.args.get('code_id',None)

    if not code_id:
        abort(403)
    name, text, image = captcha.generate_captcha()
    print(name,text,image)
    current_app.logger.debug("图片验证码内容是：%s" % text)
    try:
        redis_store.set("ImageCodeId_" + code_id, text, constants.IMAGE_CODE_REDIS_EXPIRES)
    except Exception as e:
        current_app.logger.error(e)
        abort(500)
    response = make_response(image)
    # 设置数据的类型，以便浏览器更加智能识别其是什么类型
    response.headers["Content-Type"] = "image/jpg"
    return response
@passport_blu.route('/sms_code',methods=['POST'])
def send_sms():
    mobile=request.json.get('mobile')
    code_id=request.json.get('code_id')
    input_code=request.json.get('input_code')
    if not all([mobile, code_id, input_code]):
        # 参数不全
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")
    if not re.match("^1[3578][0-9]{9}$", mobile):
        # 提示手机号不正确
        return jsonify(errno=RET.DATAERR, errmsg="手机号不正确")
    try:
        real_image_code = redis_store.get("ImageCodeId_" + code_id)
        # 如果能够取出来值，删除redis中缓存的内容
        if real_image_code:
            real_image_code = real_image_code.decode()
            redis_store.delete("ImageCodeId_" + code_id)
    except Exception as e:
        current_app.logger.error(e)
        # 获取图片验证码失败
        return jsonify(errno=RET.DBERR, errmsg="获取图片验证码失败")
    if not real_image_code:
        # 验证码已过期
        return jsonify(errno=RET.NODATA, errmsg="验证码失效")
    if input_code.lower() != real_image_code.lower():
        # 验证码输入错误
        return jsonify(errno=RET.DATAERR, errmsg="验证码输入错误")
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库查询错误")
    if user:
        # 该手机已被注册
        return jsonify(errno=RET.DATAEXIST, errmsg="该手机已被注册")
    result = random.randint(0, 999999)
    sms_code = "%06d" % result
    current_app.logger.debug("短信验证码的内容：%s" % sms_code)
    # result = CCP().send_template_sms(mobile, [sms_code, constants.SMS_CODE_REDIS_EXPIRES / 60], "1")
    # if result != 0:
    #     # 发送短信失败
    #     return jsonify(errno=RET.THIRDERR, errmsg="发送短信失败")
    try:
        redis_store.set("SMS_" + mobile, sms_code, constants.SMS_CODE_REDIS_EXPIRES)
    except Exception as e:
        current_app.logger.error(e)
        # 保存短信验证码失败
        return jsonify(errno=RET.DBERR, errmsg="保存短信验证码失败")

        # 7. 返回发送成功的响应
    return jsonify(errno=RET.OK, errmsg="发送成功",sms_code=sms_code)
@passport_blu.route('/register', methods=["POST"])
def register():
    mobile=request.json.get('mobile')
    sms_code=request.json.get('sms_code')
    password=request.json.get('password')

    if not all([mobile,sms_code,password]):
        return jsonify(errno=RET.PARAMERR,errmsg='参数不全')
    try:
        real_sms_code=redis_store.get("SMS_"+mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR,errmsg="获取服务器验证码失败")
    print(real_sms_code)
    if not real_sms_code:
        return jsonify(errno=RET.NODATA,errmsg="短信验证码无效")
    print(mobile, sms_code, real_sms_code)
    if sms_code != real_sms_code.decode():
        return jsonify(errno=RET.DATAERR, errmsg="短信验证码错误")
        # 删除短信验证码
    try:
        redis_store.delete("SMS_" + mobile)
    except Exception as e:
        current_app.logger.error(e)
    user = User()
    user.nick_name = mobile
    user.mobile = mobile
    # 对密码进行处理
    user.password = password

    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        # 数据保存错误
        return jsonify(errno=RET.DATAERR, errmsg="数据保存错误")
    # 5. 保存用户登录状态
    # session[str(user.id)] = {"user_id": user.id, "nick_name": user.nick_name, "mobile": user.mobile}
    session["user_id"] = user.id
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile

    # 6. 返回注册结果
    return jsonify(errno=RET.OK, errmsg="OK")
@passport_blu.route('/login', methods=["POST"])
def login():
    """
    1. 获取参数和判断是否有值
    2. 从数据库查询出指定的用户
    3. 校验密码
    4. 保存用户登录状态
    5. 返回结果
    :return:
    """

    # 1. 获取参数和判断是否有值
    mobile = request.json.get("mobile")

    password=request.json.get("password")
    if not all([mobile, password]):
        # 参数不全
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据错误")

    if not user:
        return jsonify(errno=RET.USERERR, errmsg="用户不存在")
    if not user.check_passowrd(password):
        return jsonify(errno=RET.PWDERR, errmsg="密码错误")
    # session[str(user.id)]={"user_id":user.id,"nick_name":user.nick_name,"mobile":user.mobile}
    session["user_id"] = user.id
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile
    session["is_admin"]=user.is_admin
    # session["is_login"]=True
    # 记录用户最后一次登录时间
    user.last_login = datetime.now()
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
    # 5. 登录成功
    return jsonify(errno=RET.OK, errmsg="OK")
@passport_blu.route("/logout")
def logout():
    """
    清除session中的对应登录之后保存的信息
    :return:
    """
    session.pop('user_id',None)
    session.pop('nick_name', None)
    session.pop('mobile', None)
    session.pop('is_admin', None)
    # session.pop('is_login',None)

    # 返回结果
    return jsonify(errno=RET.OK, errmsg="OK")