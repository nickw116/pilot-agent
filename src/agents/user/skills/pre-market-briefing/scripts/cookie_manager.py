"""
Cookie管理模块
用于管理盘前纪要API的Cookie
"""

import json
import os
import sys
from datetime import datetime, timedelta

class CookieManager:
    """Cookie管理器"""
    
    def __init__(self, cookie_file=None):
        self.cookie_file = cookie_file or os.path.join(os.path.dirname(__file__), 'cookies.json')
        self.cookies = {}
        self._load_cookies()
    
    def _load_cookies(self):
        """从文件加载Cookie"""
        if os.path.exists(self.cookie_file):
            try:
                with open(self.cookie_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        # 旧格式：列表格式
                        for cookie in data:
                            self.cookies[cookie['name']] = {
                                'value': cookie['value'],
                                'domain': cookie.get('domain', ''),
                                'path': cookie.get('path', '/'),
                                'expires': cookie.get('expires', None)
                            }
                    elif isinstance(data, dict):
                        # 新格式：字典格式
                        self.cookies = data
                    print(f"已加载 {len(self.cookies)} 个Cookie", file=sys.stderr)
            except Exception as e:
                print(f"加载Cookie文件失败: {e}", file=sys.stderr)
    
    def _save_cookies(self):
        """保存Cookie到文件"""
        try:
            with open(self.cookie_file, 'w') as f:
                json.dump(self.cookies, f, indent=2)
            print("Cookie已保存", file=sys.stderr)
        except Exception as e:
            print(f"保存Cookie失败: {e}", file=sys.stderr)
    
    def get_cookie(self, name):
        """获取Cookie值"""
        if name in self.cookies:
            return self.cookies[name]['value']
        return None
    
    def set_cookie(self, name, value, domain='', path='/', expires=None):
        """设置Cookie"""
        self.cookies[name] = {
            'value': value,
            'domain': domain,
            'path': path,
            'expires': expires
        }
        self._save_cookies()
    
    def parse_cookie_string(self, cookie_string):
        """解析Cookie字符串"""
        cookies = cookie_string.split(';')
        for cookie in cookies:
            cookie = cookie.strip()
            if '=' in cookie:
                name, value = cookie.split('=', 1)
                self.set_cookie(name.strip(), value.strip())
    
    def get_cookie_string(self):
        """获取Cookie字符串"""
        cookie_parts = []
        for name, cookie in self.cookies.items():
            cookie_parts.append(f"{name}={cookie['value']}")
        return "; ".join(cookie_parts)
    
    def is_expired(self, name):
        """检查Cookie是否过期"""
        if name not in self.cookies:
            return True
        
        cookie = self.cookies[name]
        if cookie['expires'] is None:
            return False
        
        try:
            expires = datetime.fromisoformat(cookie['expires'])
            return datetime.now() > expires
        except:
            return False
    
    def clear_expired(self):
        """清除过期的Cookie"""
        expired_names = []
        for name in self.cookies:
            if self.is_expired(name):
                expired_names.append(name)
        
        for name in expired_names:
            del self.cookies[name]
        
        if expired_names:
            self._save_cookies()
            print(f"已清除 {len(expired_names)} 个过期Cookie", file=sys.stderr)

# 全局实例
cookie_manager = CookieManager()

def get_cookie(name):
    """获取Cookie值"""
    return cookie_manager.get_cookie(name)

def set_cookie(name, value, domain='', path='/', expires=None):
    """设置Cookie"""
    cookie_manager.set_cookie(name, value, domain, path, expires)

def parse_cookie_string(cookie_string):
    """解析Cookie字符串"""
    cookie_manager.parse_cookie_string(cookie_string)

def get_cookie_string():
    """获取Cookie字符串"""
    return cookie_manager.get_cookie_string()
