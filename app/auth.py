#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import session, redirect, url_for, abort, render_template

def auth(f):
    """Authentication decorator"""
    def auth_f(*args, **keywords):        
        # 检查用户是否已经登录。
        if 'user' not in session:
            return render_template('login.html', error_msg="")
            #return redirect(url_for('login'))

        return f(*args, **keywords)

    auth_f.__name__ = f.__name__
    auth_f.__doc__ = f.__doc__
    auth_f.__dict__.update(f.__dict__)

    return auth_f