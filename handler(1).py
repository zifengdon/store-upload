#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
瑞幸咖啡门店日周清返图上传服务
阿里云函数计算 FC 3.0 - 标准Web函数

版本: FC 3.0
运行时: Python 3.9
入口: handler.handler
"""

import os
import json
import base64
import urllib.request
import urllib.error

# ==================== 配置区域 ====================
# 飞书应用配置 - 建议使用环境变量
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "cli_aac179ad3121dcda")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
BASE_TOKEN = os.environ.get("BASE_TOKEN", "UtZ6bxeyXam0gUspbCscKT4onTf")
TABLE_ID = os.environ.get("TABLE_ID", "tblwsp90DspGrnxv")
# ================================================

FEISHU_API_HOST = "https://open.feishu.cn"


def get_tenant_access_token():
    """获取飞书访问令牌"""
    url = f"{FEISHU_API_HOST}/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = json.dumps({
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("code") == 0:
                return result.get("tenant_access_token")
            print(f"获取token失败: {result}")
            return None
    except Exception as e:
        print(f"获取token异常: {e}")
        return None


def upload_file_to_feishu(file_data, file_name, token):
    """上传文件到飞书云空间，返回file_token"""
    url = f"{FEISHU_API_HOST}/open-apis/im/v1/files"
    
    # 构建multipart/form-data请求
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    
    body = f"--{boundary}\r\n"
    body += f'Content-Disposition: form-data; name="file_name"\r\n\r\n'
    body += f"{file_name}\r\n"
    body += f"--{boundary}\r\n"
    body += f'Content-Disposition: form-data; name="file_type"\r\n\r\n'
    body += "image\r\n"
    body += f"--{boundary}\r\n"
    body += f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
    body += "Content-Type: image/jpeg\r\n\r\n"
    
    if isinstance(file_data, str):
        file_data = file_data.encode("utf-8")
    body = body.encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    }
    
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("code") == 0:
                return result.get("data", {}).get("file_token")
            print(f"上传文件失败: {result}")
            return None
    except Exception as e:
        print(f"上传文件异常: {e}")
        return None


def create_base_record(fields, token):
    """在多维表格中创建记录"""
    url = f"{FEISHU_API_HOST}/open-apis/base/v3/bases/{BASE_TOKEN}/tables/{TABLE_ID}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = json.dumps({"fields": fields}).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("code") == 0
    except Exception as e:
        print(f"创建记录异常: {e}")
        return False


def handler(event, context):
    """
    FC 3.0 标准函数入口
    
    Args:
        event: 请求事件
        context: 上下文信息
    
    Returns:
        dict: 响应数据
    """
    # 设置CORS头
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }
    
    # 处理OPTIONS预检请求
    if hasattr(event, 'headers'):
        method = event.headers.get('method', event.headers.get('x-sdk-invocation-source', ''))
        if method == 'OPTIONS' or 'OPTIONS' in str(event.headers):
            return {
                "statusCode": 200,
                "headers": {**cors_headers, "Content-Type": "application/json"},
                "body": ""
            }
    
    # 解析请求
    try:
        if isinstance(event, dict):
            # FC 3.0 事件格式
            http_method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
            path = event.get("requestContext", {}).get("http", {}).get("path", "/")
            body = event.get("body", "")
            if body and isinstance(body, str):
                body = body.encode("utf-8")
        else:
            # 处理bytes类型的event
            http_method = "POST"
            path = "/api/submit"
            body = event if isinstance(event, bytes) else str(event).encode("utf-8")
    except Exception as e:
        print(f"解析请求异常: {e}")
        return {
            "statusCode": 400,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps({"error": "Invalid request"})
        }
    
    # GET请求 - 健康检查
    if http_method == "GET" or path == "/":
        return {
            "statusCode": 200,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps({
                "status": "ok",
                "message": "服务正常运行",
                "version": "FC 3.0"
            })
        }
    
    # POST请求 - 处理图片上传
    if http_method == "POST" and "/api/submit" in path:
        try:
            # 解析请求体
            if not body:
                return {
                    "statusCode": 400,
                    "headers": {**cors_headers, "Content-Type": "application/json"},
                    "body": json.dumps({"success": False, "error": "请求体为空"})
                }
            
            body_str = body.decode("utf-8") if isinstance(body, bytes) else body
            data = json.loads(body_str)
            
            store_name = data.get("storeName", "")
            report_date = data.get("reportDate", "")
            daily_photos = data.get("dailyPhotos", [])
            weekly_photos = data.get("weeklyPhotos", [])
            
            print(f"收到提交: 门店={store_name}, 日期={report_date}")
            print(f"日清图片={len(daily_photos)}张, 周清图片={len(weekly_photos)}张")
            
            # 获取飞书访问令牌
            token = get_tenant_access_token()
            if not token:
                return {
                    "statusCode": 500,
                    "headers": {**cors_headers, "Content-Type": "application/json"},
                    "body": json.dumps({"success": False, "error": "获取访问令牌失败"})
                }
            
            # 处理日清返图
            daily_file_tokens = []
            for i, photo in enumerate(daily_photos):
                if isinstance(photo, str) and photo.startswith("data:"):
                    try:
                        header, data_part = photo.split(",", 1)
                        file_data = base64.b64decode(data_part)
                        file_name = f"日清返图_{report_date.replace('-', '')}_{i+1}.jpg"
                        file_token = upload_file_to_feishu(file_data, file_name, token)
                        if file_token:
                            daily_file_tokens.append({"file_token": file_token})
                            print(f"日清图片{i+1}上传成功: {file_token}")
                    except Exception as e:
                        print(f"处理日清图片{i}失败: {e}")
            
            # 处理周清返图
            weekly_file_tokens = []
            for i, photo in enumerate(weekly_photos):
                if isinstance(photo, str) and photo.startswith("data:"):
                    try:
                        header, data_part = photo.split(",", 1)
                        file_data = base64.b64decode(data_part)
                        file_name = f"周清返图_{report_date.replace('-', '')}_{i+1}.jpg"
                        file_token = upload_file_to_feishu(file_data, file_name, token)
                        if file_token:
                            weekly_file_tokens.append({"file_token": file_token})
                            print(f"周清图片{i+1}上传成功: {file_token}")
                    except Exception as e:
                        print(f"处理周清图片{i}失败: {e}")
            
            # 转换日期格式 (2024-01-15 -> 2024/01/15)
            date_str = report_date.replace("-", "/")
            
            # 构建记录字段
            fields = {
                "门店": store_name,
                "日期": date_str,
            }
            
            if daily_file_tokens:
                fields["日清返图"] = daily_file_tokens
            if weekly_file_tokens:
                fields["周清返图"] = weekly_file_tokens
            
            # 创建记录
            success = create_base_record(fields, token)
            
            if success:
                print(f"记录创建成功: 门店={store_name}, 日期={date_str}")
                return {
                    "statusCode": 200,
                    "headers": {**cors_headers, "Content-Type": "application/json"},
                    "body": json.dumps({"success": True})
                }
            else:
                return {
                    "statusCode": 500,
                    "headers": {**cors_headers, "Content-Type": "application/json"},
                    "body": json.dumps({"success": False, "error": "创建记录失败"})
                }
                
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            return {
                "statusCode": 400,
                "headers": {**cors_headers, "Content-Type": "application/json"},
                "body": json.dumps({"success": False, "error": "无效的JSON格式"})
            }
        except Exception as e:
            print(f"处理请求异常: {e}")
            import traceback
            traceback.print_exc()
            return {
                "statusCode": 500,
                "headers": {**cors_headers, "Content-Type": "application/json"},
                "body": json.dumps({"success": False, "error": str(e)})
            }
    
    # 其他路径返回404
    return {
        "statusCode": 404,
        "headers": {**cors_headers, "Content-Type": "application/json"},
        "body": json.dumps({"error": "Not Found"})
    }


# ==================== 本地测试入口 ====================
if __name__ == "__main__":
    # 本地测试用
    print("=" * 50)
    print("本地测试服务器")
    print("请访问: http://localhost:9000")
    print("=" * 50)
    
    from wsgiref.simple_server import make_server
    
    def local_handler(environ, start_response):
        """本地WSGI处理器"""
        from io import BytesIO
        
        method = environ.get("REQUEST_METHOD")
        path = environ.get("PATH_INFO")
        
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Access-Control-Allow-Origin", "*"),
        ]
        
        if method == "GET":
            response_body = json.dumps({
                "status": "ok",
                "message": "本地测试服务正常运行"
            }).encode("utf-8")
            start_response("200 OK", headers)
            return [response_body]
        
        if method == "POST" and "/api/submit" in path:
            try:
                content_length = int(environ.get("CONTENT_LENGTH", 0))
                body = environ.get("wsgi.input").read(content_length)
                
                # 调用主handler
                event = {
                    "requestContext": {
                        "http": {"method": "POST", "path": path}
                    },
                    "body": body.decode("utf-8")
                }
                
                result = handler(event, None)
                response_body = result.get("body", "").encode("utf-8")
                start_response(str(result.get("statusCode", 200)) + " OK", headers)
                return [response_body]
            except Exception as e:
                response_body = json.dumps({"error": str(e)}).encode("utf-8")
                start_response("500 OK", headers)
                return [response_body]
        
        response_body = json.dumps({"error": "Not Found"}).encode("utf-8")
        start_response("404 OK", headers)
        return [response_body]
    
    port = 9000
    server = make_server("0.0.0.0", port, local_handler)
    server.serve_forever()
