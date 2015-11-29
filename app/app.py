#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import getopt
import pytz
from bson import ObjectId
from datetime import datetime
from publicsuffixlist import PublicSuffixList
import md5

from flask import Flask, request, render_template, redirect, url_for,session
from flask.ext.pymongo import PyMongo
from auth import auth

PAGE_ITEM = 50
psl = PublicSuffixList()

mongo = PyMongo()

app = Flask(__name__)
app.secret_key = \
    '\xfd{H\\xe5<\x95\xf9\xe3\x96.5\xd1\x01o<!\xd5\xa2\x9fR"\xa1\xa8'

# config this app from file.
app.config.from_pyfile('config.py')

# init mongodb connection.
#mongo.init_app(app)
mongo = PyMongo(app)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html', error_msg="")

    error=None
    uname  = request.form['acct']
    passwd = request.form['pw']
    goto = request.form['goto']
    creating = request.form.get('creating','f')

    if creating == 't':
        if find_user(uname):
            error = u"用户名已存在，请换一个。"
        else:
            add_status = create_user(uname, passwd)
            if not add_status:
                error=u"添加失败，请重试。"
    else:
        if not valid_login(uname, passwd):
            error = u'登录失败，请重试。'

    if error is not None:
        return render_template('login.html', 
                        error_msg=error)
    else:
        session['user'] = uname
        return redirect(url_for(goto))


@app.route("/logout", methods=['GET'])
@auth
def logout():
    session.pop('user', None)
    return redirect(url_for('newest'))

@app.route("/submit", methods=['GET'])
@auth
def submit():
    return render_template('submit.html')     

@app.route("/r", methods=['POST'])
@auth
def r():
    ban={}
    error = None
    ban, error = _ban_content_valid(request.form)
    if error is None:
        add_status = add_ban(ban)
        if not add_status:
            error = add_status
    if error is None:
        return redirect(url_for('newest'))
    else:
        return u'遇到错误请返回重新提交:'+error
        
@app.route("/newest/<page>", methods=['GET'])
def more(page=1):
    bans = get_bans(page)
    return render_template('list.html', bans=bans, page=int(page)+1)    

        
@app.route("/newest", methods=['GET'])
def newest(page=1):
    bans = get_bans(page)
    return redirect(url_for('more', page=1))   


@app.route("/", methods=['GET'])
def hello():
    return redirect(url_for('newest', page=1))

@app.route("/ban/<ban_id>", methods=['GET'])
def ban(ban_id):
    ban = get_ban(ban_id)
    comments = gen_ban_comments(get_comments(ban_id))
    print "comments:", comments
    if not ban:
        return u"没找到信息，请返回。"
    return render_template('ban.html', ban=ban, comments=comments)

@app.route("/comment", methods=['POST'])
@auth
def comment():
    error = None
    try:
        comment = request.form.get("text")
        ban_id = request.form.get("ban_id")
        if isinstance(comment, unicode):
            comment = comment.encode("UTF-8")
        if len(comment) == 0:
            error = u'内容不能为空。'
        else:
            add_status = add_comment(ban_id, comment)
            if add_status:
                add_inc_comment_to_ban(ban_id)
            else:
                error = add_status
    except Exception, e:
        error = e
    finally:
        if error is None:
            return redirect(url_for('ban',ban_id=ban_id))
        else:
            return u'遇到错误请返回重新提交:'+error    

@app.route("/edit/<ban_id>", methods=['GET'])
@auth
def edit(ban_id):
    ban = get_ban(ban_id)
    if not ban:
        return u"没找到信息，请返回。"
    return render_template('edit.html', ban=ban)

@app.route("/xedit", methods=['POST'])
@auth
def xedit():
    error = None
    ban_id = request.form.get("ban_id")
    ban, error = _ban_content_valid(request.form)
    if error is None:
        status = update_ban(ban_id, ban)
        error = status if not status else None
    if error is None:
        return redirect(url_for('edit', ban_id=ban_id))
    else:
        return error


@app.route("/delete-confirm/<ban_id>", methods=['GET'])
@auth
def delete(ban_id):
    goto = request.args.get("goto")
    ban = get_ban(ban_id)
    if not ban:
        return u"没找到信息，请返回。"
    return render_template('delete-confirm.html', ban=ban, goto=goto)

@app.route("/xdelete", methods=['POST'])
@auth
def xdelete():
    ban_id = request.form.get("ban_id")
    d=request.form.get("d")
    goto = request.form.get("goto", "newest")
    __parm={}
    if d == "Yes":
        status = del_ban(ban_id)
        if status:
            return redirect(url_for('newest'))
        else:   
            return u'发生错误，请返回重试。'
    else:
        if goto in ["edit", "ban"]:
            __parm = dict(ban_id=ban_id)
        if goto in ['submitted', 'comments']:
            __parm = dict(name=session['user'], page=1)
        return redirect(url_for(goto, **__parm))


@app.route("/editcmt/<comment_id>", methods=['GET'])
@auth
def editcmt(comment_id):
    comment = get_comment(comment_id)
    if not comment:
        return u"没找到信息，请返回。"
    return render_template('editcmt.html', comment=comment)


@app.route("/xeditcmt", methods=['POST'])
@auth
def xeditcmt():
    error = None
    comment_id = request.form.get("comment_id")
    comment = request.form.get("text")
    comment = comment.encode("UTF-8") if isinstance(comment, unicode) else comment
    if len(comment) == 0:
        error = u"内容不能为空。"
    if error is None:
        status = update_comment(comment_id, comment)
        error = status if not status else None
    if error is None:
        return redirect(url_for('editcmt', comment_id=comment_id))
    else:
        return error


@app.route("/deletecmt-confirm/<comment_id>", methods=['GET'])
@auth
def deletecmt(comment_id):
    goto = request.args.get("goto")
    comment = get_comment(comment_id)
    if not comment:
        return u"没找到信息，请返回。"
    return render_template('deletecmt-confirm.html', comment=comment, goto=goto)

@app.route("/xdeletecmt", methods=['POST'])
@auth
def xdeletecmt():
    comment_id = request.form.get("comment_id")
    ban_id = request.form.get("ban_id")
    d=request.form.get("d")
    goto = request.form.get("goto", "ban")
    __parm={}
    if d == "Yes":
        status = delete_comment(comment_id)
        if status:
            div_inc_comment_to_ban(ban_id)
            return redirect(url_for('ban', ban_id=ban_id))
        else:   
            return u'发生错误，请返回重试。'
    else:
        if goto in ["edit", "ban"]:
            __parm = dict(ban_id=ban_id)
        if goto in ['editcmt']:
            __parm = dict(comment_id=comment_id)
        if goto in ['submitted', 'comments']:
            __parm = dict(name=session['user'], page=1)
        return redirect(url_for(goto, **__parm))

@app.route("/user/<name>", methods=['GET'])
@auth
def user(name):
    user = get_user(name)
    return render_template('user.html', user=user)

@app.route("/xuser", methods=['POST'])
@auth
def xuser():
    user_id = request.form.get('user_id')
    name = request.form.get('name')
    bio = request.form.get('bio')
    email = request.form.get('uemail','')
    bio = bio.encode('UTF-8') if isinstance(bio, unicode) else bio
    doc={"bio":bio, "email":email}
    status = update_user(user_id, doc)
    error = status if not status else None
    if error is None:
        return redirect(url_for('user', name=name))
    else:
        return error


@app.route("/changepw", methods=['GET'])
@auth
def changepw():
    user=get_user(session['user'])
    return render_template("changepw.html", user_id=user.get('user_id') )

@app.route("/c", methods=['POST'])
@auth
def c():
    user_id = request.form.get('fnid')
    oldpw = request.form.get('oldpw')
    pw = request.form.get('pw')
    error = None

    user=get_user_with_id(user_id)
    if user['passwd'] != oldpw:
        error = u'原密码错误'
    if error is None:
        doc = {"passwd":md5.new(passwd).hexdigest()}
        status = update_user(user_id, doc)
        error = status if not status else None
    if error is None:
        return redirect(url_for('newest'))
    else:
       return render_template("changepw.html", user_id=user.get('user_id'), error=error )


@app.route("/forgot", methods=['GET'])
def forgot():
    return render_template("forgot.html")

@app.route("/x", methods=['POST'])
def x():
    name = request.form.get('s')
    user = get_user(name)
    if not user:
        return u"用户不存在"
    #send mail
    #TODO: send mail
    return render_template("x.html" )

@app.route("/vote/<up_down>/<ban_id>", methods=['GET'])
@auth
def vote(up_down, ban_id):
    if up_down == "up":
        vote_up(ban_id, name)
    return redirect(url_for("newest", page=1))

@app.route("/comments/<name>/<page>", methods=['GET'])
@auth
def comments(name, page=1):
    comments = get_comments_with_user(name, page)
    return render_template("comments.html", comments=comments, name=name, page=1)

@app.route("/submitted/<name>/<page>", methods=['GET'])
@auth
def submitted(name, page=1):
    bans = get_bans_with_user(name, page)
    return render_template('submitted.html', bans=bans, name=name, page=int(page)+1)    

@app.route("/welcome", methods=['GET'])
def welcome():
    return render_template("welcome.html")

@app.route("/guidelines", methods=['GET'])
def newsguidelines():
    return render_template("guidelines.html")

@app.route("/faq", methods=['GET'])
def faq():
    return render_template("faq.html")

@app.route("/security", methods=['GET'])
def security():
    return render_template("security.html")


def vote_up(ban_id, name):
    return mongo.db.ban.update({"_id":ObjectId(ban_id)},
                                {"$addToSet":{"vote":{"$each":[name]}} }, w=1)

def get_user_with_id(user_id):
    u =  mongo.db.user.find_one({"_id":ObjectId(user_id)})
    return _gen_user_info(u)

def get_user(name):
    u = mongo.db.user.find_one({"name":name})
    return _gen_user_info(u)

def _gen_user_info(u):
    if not u: return {}
    return dict(
                user_id=str(u.get('_id')),
                name=str(u.get('name')),
                bio=u.get('bio',''),
                email=u.get('email',''),
                karma=u.get('karma',0),
                passwd=u.get('passwd'),
                created_at=gen_by_created_at(u.get("created_at"))
                )

def update_user(user_id, doc):
    return mongo.db.user.update({"_id":ObjectId(user_id)},
                                {"$set":doc}, w=1)

def _ban_content_valid(req):
    ban={}
    error=None   
    ban["url"] = req.get("url")
    ban["site"] =  psl.privatesuffix(ban["url"])  # "example.com"
    title = req.get("title")
    text = req.get("text")
    ban["title"] = title.encode("UTF-8") if isinstance(title, unicode) else title            
    ban["text"] = text.encode("UTF-8") if isinstance(text, unicode) else text            
    if len(title) == 0 and len(text) == 0 and len(url) == 0:
        error = u'内容不能为空。'
    ban["author"]=session["user"]
    ban["created_at"]=datetime.utcnow()
    return ban, error

def add_comment(ban_id, text):
    "add new comment "
    author = session['user']
    comment = dict(ban_id=ObjectId(ban_id),
                 comment=text, 
                 author=author, 
                 created_at=datetime.utcnow()
                )
    return mongo.db.comments.insert(comment, w=1)

def add_inc_comment_to_ban(ban_id):
    return mongo.db.ban.update({"_id":ObjectId(ban_id)}, 
                                {"$inc":{"comments":1}}, 
                                w=1)

def div_inc_comment_to_ban(ban_id):
    return mongo.db.ban.update({"_id":ObjectId(ban_id)}, 
                                {"$inc":{"comments":-1}}, 
                                w=1)

def add_ban(ban):
    "add new ban"
    return mongo.db.ban.insert(ban, w=1)

def update_ban(ban_id, ban):
    "update new ban"
    return mongo.db.ban.update(
                            {"_id":ObjectId(ban_id)}, 
                            {"$set":ban}, 
                            w=1)

def get_comments_with_user(name, page):
    cmts = []
    comments = mongo.db.comments.find({"author": name},
        sort=([("created_at",-1)]),
        skip=int(page)*PAGE_ITEM if int(page) > 1 else 0,
        limit=PAGE_ITEM
        )
    for c in comments:
        cmts.append( _gen_comment(c) )
    return cmts

    

def get_comments(ban_id):
    return mongo.db.comments.find({"ban_id": ObjectId(ban_id)})

def get_comment(comment_id):
    "get comment info"
    r = mongo.db.comments.find_one({"_id": ObjectId(comment_id)})
    if r:
        comment = _gen_comment(r) 
    return comment

def _gen_comment(c):
    return dict(
                comment_id=str(c.get('_id')),
                ban_id=str(c.get('ban_id')),
                comment=c.get('comment',0),
                author=c.get('author'),
                created_at=gen_by_created_at(c.get("created_at"))
                )

def delete_comment(comment_id):
    return mongo.db.comments.remove({"_id": ObjectId(comment_id)})

def update_comment(comment_id, text):
    return mongo.db.comments.update({"_id": ObjectId(comment_id)}, 
                                {"$set":{"comment":text}}, 
                                w=1)

def gen_ban_comments(comments):
    cmts = []
    for c in comments:
        cmts.append( _gen_comment(c) )
    return cmts

def del_ban(ban_id):
    "delete ban"
    return mongo.db.ban.remove({"_id":ObjectId(ban_id)})

def get_ban(ban_id):
    "get ban info"
    r = mongo.db.ban.find_one({"_id":ObjectId(ban_id)})
    ban = _gen_ban(r) if r else {}
    return ban

def get_bans(page):
    "get ban list"
    res = mongo.db.ban.find({},
        sort=([("created_at",-1)]),
        skip=int(page)*PAGE_ITEM if int(page) > 1 else 0,
        limit=PAGE_ITEM
        )
    bans = []
    for r in res:
        bans.append( _gen_ban(r) )            
    return bans    

def get_bans_with_user(name, page):
    "get ban list"
    res = mongo.db.ban.find({"author":name},
        sort=([("created_at",-1)]),
        skip=int(page)*PAGE_ITEM if int(page) > 1 else 0,
        limit=PAGE_ITEM
        )
    bans = []
    for r in res:
        bans.append( _gen_ban(r) )            
    return bans    

def _gen_ban(b):
    name = session.get('user')
    return dict(
        rank=b.get("rank", 1),
        ban_id=str(b.get("_id")),
        title=b.get("title","no title"),
        url=b.get("url",None),
        text=b.get("text",None),
        site=b.get("site", "no site"),
        comments=b.get("comments",0),
        author=b.get("author", "unknow"),
        voted=_voted(b, name),
        created_at=gen_by_created_at(b.get("created_at")),
        points=b.get("points", 0)
        )

def _voted(ban,name):
    return name in ban.get('vote',[]) or ban['author'] == name

def valid_login(uname, passwd):
    pw = md5.new(passwd).hexdigest()
    return mongo.db.user.find_one({"name":uname, "passwd":pw})

def find_user(uname):
    return mongo.db.user.find_one({"name":uname})

def create_user(uname, passwd):
    pw = md5.new(passwd).hexdigest()
    return mongo.db.user.insert(
                        {  "name":uname, 
                            "passwd":pw, 
                            "created_at": datetime.utcnow()}, 
                        w=1)

def gen_by_created_at(created_at):
    "gen to x mins/hours/days by"
    tz=pytz.timezone('Asia/Shanghai')
    ago = datetime.now(tz) - created_at.astimezone(tz)
    if ago.days > 0:
        return str(ago.days)+u"天"
    else:
        if ago.seconds < 3600:
            return str(ago.seconds/60) + u"分钟"
        else:
            return str(ago.seconds/3600) + u"小时"


default_port = 50000
opts, args = getopt.getopt(sys.argv[1:], 'p:', ["port="])
for opt, value in opts:
    if opt == '--port':
       	default_port = int(value)

if __name__ == "__main__":
    app.debug = True
    app.run(host='0.0.0.0', port=default_port)


