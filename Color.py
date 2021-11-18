#!/usr/bin/env python
# -*- coding: utf-8 -*-
# author:zml

def Colors(text, fcolor=None,bcolor=None,style=None):
    '''
    自定义字体样式及颜色
    '''
    # 字体颜色
    fg={
       'black': '\033[30m',     #字体黑
       'red': '\033[31m',       #字体红
       'green': '\033[32m',     #字体绿
       'yellow': '\033[33m',    #字体黄
       'blue': '\033[34m',      #字体蓝
       'magenta': '\033[35m',   #字体紫
       'cyan': '\033[36m',      #字体青
       'white':'\033[37m',      #字体白
        'end':'\033[0m'         #默认色
    }
    # 背景颜色
    bg={
       'black': '\033[40m',     #背景黑
       'red': '\033[41m',       #背景红
       'green': '\033[42m',     #背景绿
       'yellow': '\033[43m',    #背景黄
       'blue': '\033[44m',      #背景蓝
       'magenta': '\033[45m',   #背景紫
       'cyan': '\033[46m',      #背景青
       'white':'\033[47m',      #背景白
    }
    # 内容样式
    st={
        'bold': '\033[1m',      #高亮
        'url': '\033[4m',       #下划线
        'blink': '\033[5m',     #闪烁
        'seleted': '\033[7m',   #反显
    }

    if fcolor in fg:
        text=fg[fcolor]+text+fg['end']
    if bcolor in bg:
        text = bg[bcolor] + text + fg['end']
    if style in st:
        text = st[style] + text + fg['end']
    return text
