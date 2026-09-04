from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import shutil
import re
import json
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
CORS(app)

# ==================== 全局变量 ====================
staff = {}
document = {}
staffCount = 0
documentCount = 0
classification_basis = {}
classification_officers = {}
audit_logs = []
secret_points = {}
classification_records = []

DIRS = {
    'unknown': './Unknown/',
    'secret': './Secret/',
    'confidential': './Confidential/',
    'topsecret': './Top-secret/',
    'unclassified': './Unclassified/',
    'use': './Use/'
}

# ==================== 增强版敏感词库 ====================
SENSITIVE_KEYWORDS_ENHANCED = {
    "绝密": {
        "keywords": ["核武器", "导弹", "军事部署", "情报来源", "密码算法", "领导人行程", 
                     "核弹头", "战略武器", "国防动员", "战争计划", "核设施", "东风导弹",
                     "战略核潜艇", "洲际导弹", "核威慑", "作战指令", "最高权限", "中央军委",
                     "国防部", "作战方案", "军事行动", "国家机密", "核心机密"],
        "weight": 10
    },
    "机密": {
        "keywords": ["国防预算", "武器装备", "作战计划", "外交谈判", "经济数据", "军事基地",
                     "部队调动", "情报人员", "反恐行动", "网络安全", "军工企业", "武器参数",
                     "战术部署", "演习方案", "应急预案", "密码本", "加密算法", "涉密人员",
                     "保密检查", "安全审查", "内部通报", "专案组"],
        "weight": 7
    },
    "秘密": {
        "keywords": ["内部会议", "人事任免", "项目进展", "技术参数", "合同细节", "内部文件",
                     "工作方案", "调查报告", "审计报告", "涉密人员", "保密协议", "未公开",
                     "内部讨论", "会议纪要", "征求意见", "草案", "试行", "内部资料",
                     "工作秘密", "商业秘密", "内部掌握"],
        "weight": 4
    }
}

CLASSIFICATION_MARKERS = {
    "绝密": ["绝密", "★绝密", "【绝密】", "绝密★", "核心机密", "绝密级"],
    "机密": ["机密", "★机密", "【机密】", "机密★", "重要机密", "机密级"],
    "秘密": ["秘密", "★秘密", "【秘密】", "秘密★", "内部秘密", "秘密级"]
}

PERSONAL_PATTERNS = {
    "身份证号": r'[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]',
    "手机号": r'1[3-9]\d{9}',
    "邮箱": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    "内网IP": r'(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})',
    "银行卡号": r'[1-9]\d{15,18}',
    "护照号": r'[EePpSsGg]\d{7,8}',
    "军官证号": r'[\u4e00-\u9fa5]{2,4}字第\d+号'
}

# ==================== AI敏感信息检测 ====================
def ai_detect_sensitive(content):
    detected = []
    lines = content.split('\n')
    max_lines = min(len(lines), 500)
    
    for line_num, line in enumerate(lines[:max_lines], 1):
        if not line.strip():
            continue
        
        for level_name, markers in CLASSIFICATION_MARKERS.items():
            level_val = 3 if level_name == "绝密" else (2 if level_name == "机密" else 1)
            for marker in markers:
                if marker in line:
                    already_exists = False
                    for d in detected:
                        if d['location'] == f'第{line_num}行' and marker in d['content']:
                            already_exists = True
                            break
                    if not already_exists:
                        detected.append({
                            'content': line[:150],
                            'level': level_val,
                            'location': f'第{line_num}行',
                            'type': f'密级标识: {marker}'
                        })
                    break
        
        for level_name, level_data in SENSITIVE_KEYWORDS_ENHANCED.items():
            level_val = 3 if level_name == "绝密" else (2 if level_name == "机密" else 1)
            for keyword in level_data["keywords"]:
                if keyword in line:
                    already_exists = False
                    for d in detected:
                        if d['location'] == f'第{line_num}行' and keyword in d['content']:
                            already_exists = True
                            break
                    if not already_exists:
                        detected.append({
                            'content': line[:150],
                            'level': level_val,
                            'location': f'第{line_num}行',
                            'type': f'关键词: {keyword}'
                        })
                    break
        
        for info_type, pattern in PERSONAL_PATTERNS.items():
            matches = re.findall(pattern, line)
            if matches:
                if info_type in ["身份证号", "军官证号"]:
                    level_val = 2
                else:
                    level_val = 1
                
                already_exists = False
                for d in detected:
                    if d['location'] == f'第{line_num}行' and info_type in d['type']:
                        already_exists = True
                        break
                if not already_exists:
                    detected.append({
                        'content': f"{info_type}: {matches[0][:30] if matches[0] else '检测到'}",
                        'level': level_val,
                        'location': f'第{line_num}行',
                        'type': f'个人敏感信息: {info_type}'
                    })
                break
    
    unique = []
    seen_content = set()
    for d in detected:
        if d['content'] not in seen_content:
            seen_content.add(d['content'])
            unique.append(d)
    
    return unique[:20]

# ==================== 基础函数 ====================
def get_level_name(level):
    return {0: "非密", 1: "秘密", 2: "机密", 3: "绝密", -1: "未定密"}.get(level, "未知")

def get_current_date():
    now = datetime.now()
    return now.year * 10000 + now.month * 100 + now.day

def get_clearance_path(clearance_level):
    if clearance_level == 1:
        return DIRS['secret']
    elif clearance_level == 2:
        return DIRS['confidential']
    elif clearance_level == 3:
        return DIRS['topsecret']
    return DIRS['unknown']

def create_directories():
    for dir_path in DIRS.values():
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

def init_classification_basis():
    global classification_basis
    basis_data = [
        ("B001", "《保密法》第十三条", "国家秘密的基本范围", "法律"),
        ("B002", "《保密法》第十四条", "密级划分（绝密/机密/秘密）", "法律"),
        ("B003", "《保密法》第十六条", "定密责任人制度", "法律"),
        ("B004", "《保密法》第十七条", "定密权限", "法律"),
        ("B005", "《保密法》第二十条", "保密期限规定", "法律"),
        ("B006", "《保密法》第二十一条", "知悉范围最小化", "法律"),
        ("B007", "《保密法》第二十二条", "国家秘密标志", "法律"),
        ("B008", "《保密法》第二十三条", "密级变更", "法律"),
        ("B009", "《保密法》第二十四条", "年度审核与解密", "法律"),
        ("C001", "《保密法实施条例》第十七条", "定密程序", "行政法规"),
        ("C002", "《保密法实施条例》第二十二条", "解密与变更", "行政法规"),
        ("C003", "《保密法实施条例》第二十四条", "定密纠错", "行政法规"),
    ]
    for data in basis_data:
        classification_basis[data[0]] = type('obj', (object,), {'basis_id': data[0], 'basis_name': data[1], 'basis_content': data[2], 'basis_type': data[3]})

def quick_save_person():
    with open("Person.txt", "w", encoding='utf-8') as f:
        f.write(f"{staffCount}\n")
        for i in range(1, staffCount + 1):
            s = staff[i]
            f.write(f"{s.isAdmin} {s.username} {s.passcode} {s.clearance} {s.originalClearance} {s.authorizedBy}\n")

def quick_save_file():
    with open("File.txt", "w", encoding='utf-8') as f:
        f.write(f"{documentCount}\n")
        for i in range(1, documentCount + 1):
            d = document[i]
            know_scope = getattr(d, 'know_scope', '')
            know_persons = getattr(d, 'know_persons', '')
            know_departments = getattr(d, 'know_departments', '')
            secret_term_type = getattr(d, 'secret_term_type', '年限')
            secret_term_years = getattr(d, 'secret_term_years', 0)
            secret_term_date = getattr(d, 'secret_term_date', '')
            secret_term_condition = getattr(d, 'secret_term_condition', '')
            f.write(f"{d.name} {d.clearanceLevel} {d.expirationDate} {d.handledBy} {d.accessKey}|{secret_term_type}|{secret_term_years}|{secret_term_date}|{secret_term_condition}|{know_scope}|{know_persons}|{know_departments}\n")

def save_audit_logs():
    with open("AuditLog.txt", "w", encoding='utf-8') as f:
        for log in audit_logs:
            f.write(f"{log['time']}|{log['operator']}|{log['type']}|{log['target']}|{log['result']}|{log['details']}\n")

def add_audit_log(operator, op_type, target, result, details=""):
    audit_logs.append({
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'operator': operator,
        'type': op_type,
        'target': target,
        'result': result,
        'details': details
    })
    save_audit_logs()

# ==================== 数据加载 ====================
def load_data():
    global staffCount, documentCount, staff, document, audit_logs, secret_points
    create_directories()
    init_classification_basis()
    
    if os.path.exists("Person.txt"):
        with open("Person.txt", "r", encoding='utf-8') as f:
            lines = f.readlines()
            if lines:
                staffCount = int(lines[0].strip())
                for i in range(1, staffCount + 1):
                    if i < len(lines):
                        parts = lines[i].strip().split()
                        if len(parts) >= 6:
                            staff[i] = type('obj', (object,), {
                                'isAdmin': int(parts[0]), 
                                'username': parts[1], 
                                'passcode': parts[2], 
                                'clearance': int(parts[3]), 
                                'originalClearance': int(parts[4]), 
                                'authorizedBy': int(parts[5])
                            })
    else:
        staffCount = 1
        staff[1] = type('obj', (object,), {
            'isAdmin': 1, 
            'username': 'admin', 
            'passcode': 'admin', 
            'clearance': 3, 
            'originalClearance': 3, 
            'authorizedBy': 0
        })
        quick_save_person()
    
    if os.path.exists("File.txt"):
        with open("File.txt", "r", encoding='utf-8') as f:
            lines = f.readlines()
            if lines:
                documentCount = int(lines[0].strip())
                for i in range(1, documentCount + 1):
                    if i < len(lines):
                        line = lines[i].strip()
                        parts = line.split('|')
                        main_parts = parts[0].split()
                        if len(main_parts) >= 5:
                            secret_term_type = parts[1] if len(parts) > 1 else '年限'
                            secret_term_years = int(parts[2]) if len(parts) > 2 and parts[2] else 0
                            secret_term_date = parts[3] if len(parts) > 3 else ''
                            secret_term_condition = parts[4] if len(parts) > 4 else ''
                            know_scope = parts[5] if len(parts) > 5 else ''
                            know_persons = parts[6] if len(parts) > 6 else ''
                            know_departments = parts[7] if len(parts) > 7 else ''
                            
                            document[i] = type('obj', (object,), {
                                'name': main_parts[0], 
                                'clearanceLevel': int(main_parts[1]), 
                                'expirationDate': int(main_parts[2]), 
                                'handledBy': int(main_parts[3]), 
                                'accessKey': main_parts[4],
                                'secret_term_type': secret_term_type,
                                'secret_term_years': secret_term_years,
                                'secret_term_date': secret_term_date,
                                'secret_term_condition': secret_term_condition,
                                'know_scope': know_scope,
                                'know_persons': know_persons,
                                'know_departments': know_departments
                            })
    
    audit_logs.clear()
    if os.path.exists("AuditLog.txt"):
        with open("AuditLog.txt", "r", encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 5:
                    audit_logs.append({
                        'time': parts[0], 
                        'operator': parts[1], 
                        'type': parts[2], 
                        'target': parts[3], 
                        'result': parts[4], 
                        'details': parts[5] if len(parts) > 5 else ''
                    })
    
    secret_points.clear()
    if os.path.exists("SecretPoints.txt"):
        with open("SecretPoints.txt", "r", encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 3:
                    fn = parts[0]
                    if fn not in secret_points:
                        secret_points[fn] = []
                    secret_points[fn].append({
                        'content': parts[1], 
                        'level': int(parts[2]), 
                        'location': parts[3] if len(parts) > 3 else ''
                    })

load_data()

# ==================== 装饰器 ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or staff[session['user_id']].isAdmin != 1:
            return jsonify({'success': False, 'message': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated_function

# ==================== API 路由 ====================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    for i, s in staff.items():
        if s.username == username and s.passcode == password:
            session['user_id'] = i
            session['username'] = username
            session['is_admin'] = s.isAdmin
            session['clearance'] = s.clearance
            return jsonify({'success': True, 'is_admin': s.isAdmin == 1, 'username': username, 'clearance': get_level_name(s.clearance)})
    
    return jsonify({'success': False, 'message': '账号或密码错误'})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/user/info', methods=['GET'])
@login_required
def user_info():
    return jsonify({
        'username': session['username'],
        'is_admin': session['is_admin'],
        'clearance': get_level_name(staff[session['user_id']].clearance),
        'clearance_level': staff[session['user_id']].clearance
    })


@app.route('/api/files', methods=['GET'])
@login_required
def get_files():
    files = []
    current_user_clearance = staff[session['user_id']].clearance
    
    for i, d in document.items():
        # 权限过滤：用户只能看到密级不高于自己密级的文件
        # 未定密文件（clearanceLevel == -1）所有人都能看到
        if d.clearanceLevel > current_user_clearance and d.clearanceLevel != -1:
            continue  # 跳过密级高于用户的文件
        
        secret_term_type = getattr(d, 'secret_term_type', '年限')
        if secret_term_type == '年限':
            years = getattr(d, 'secret_term_years', 0)
            secret_term_display = f"{years}年" if years > 0 else '未设置'
        elif secret_term_type == '时间':
            secret_term_display = f"解密时间: {getattr(d, 'secret_term_date', '')}"
        else:
            secret_term_display = f"解密条件: {getattr(d, 'secret_term_condition', '')}"
        
        files.append({
            'id': i,
            'name': d.name,
            'clearance': get_level_name(d.clearanceLevel),
            'clearance_level': d.clearanceLevel,
            'expiration_date': d.expirationDate,
            'secret_term_display': secret_term_display,
            'know_scope': getattr(d, 'know_scope', ''),
            'know_persons': getattr(d, 'know_persons', ''),
            'know_departments': getattr(d, 'know_departments', '')
        })
    return jsonify({'success': True, 'files': files})

@app.route('/api/files/add', methods=['POST'])
@admin_required
def add_file():
    global documentCount
    data = request.json
    filename = data.get('filename')
    content = data.get('content', '')
    
    if not filename:
        return jsonify({'success': False, 'message': '文件名不能为空'})
    
    documentCount += 1
    document[documentCount] = type('obj', (object,), {
        'name': filename, 
        'clearanceLevel': -1, 
        'expirationDate': 0, 
        'handledBy': 0, 
        'accessKey': '2333333333',
        'secret_term_type': '年限',
        'secret_term_years': 0,
        'secret_term_date': '',
        'secret_term_condition': '',
        'know_scope': '',
        'know_persons': '',
        'know_departments': ''
    })
    
    file_path = DIRS['unknown'] + filename + ".txt"
    if content and content.strip():
        file_content = content
    else:
        file_content = f"这是一个待定密的文件：{filename}\n请对此文件进行定密操作。\n"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(file_content)
    
    quick_save_file()
    add_audit_log(session['username'], "添加文件", filename, "成功", f"待定密，内容长度:{len(file_content)}")
    
    return jsonify({'success': True, 'message': f'文件 {filename} 添加成功'})

@app.route('/api/files/classify', methods=['POST'])
@login_required
def classify_file():
    data = request.json
    filename = data.get('filename')
    level = data.get('level')
    basis_id = data.get('basis_id')
    
    # 保密期限三种形式
    secret_term_type = data.get('secret_term_type', '年限')
    secret_term_years = data.get('secret_term_years', 0)
    secret_term_date = data.get('secret_term_date', '')
    secret_term_condition = data.get('secret_term_condition', '')
    
    # 知悉范围
    know_scope = data.get('know_scope', '')
    know_persons = data.get('know_persons', '')
    know_departments = data.get('know_departments', '')
    
    file_found = None
    for i, d in document.items():
        if d.name == filename:
            file_found = i
            break
    
    if file_found is None:
        return jsonify({'success': False, 'message': '文件不存在'})
    
    if document[file_found].clearanceLevel != -1:
        return jsonify({'success': False, 'message': '文件已定密'})
    
    # 检查用户密级是否不低于目标密级
    current_user_level = staff[session['user_id']].clearance
    if current_user_level < level:
        return jsonify({'success': False, 'message': f'您的密级({get_level_name(current_user_level)})不足，无法定为{get_level_name(level)}'})
    
    # 保存定密信息
    document[file_found].clearanceLevel = level
    document[file_found].expirationDate = get_current_date()
    document[file_found].handledBy = session['user_id']
    
    # 保存保密期限
    document[file_found].secret_term_type = secret_term_type
    document[file_found].secret_term_years = secret_term_years
    document[file_found].secret_term_date = secret_term_date
    document[file_found].secret_term_condition = secret_term_condition
    
    # 保存知悉范围
    document[file_found].know_scope = know_scope
    document[file_found].know_persons = know_persons
    document[file_found].know_departments = know_departments
    
    # 移动文件到对应密级目录
    from_path = DIRS['unknown'] + filename + ".txt"
    to_path = get_clearance_path(level) + filename + ".txt"
    if os.path.exists(from_path):
        shutil.copy2(from_path, to_path)
        os.remove(from_path)
    
    # 生成保密期限显示文本
    if secret_term_type == '年限':
        term_display = f"{secret_term_years}年"
    elif secret_term_type == '时间':
        term_display = f"解密时间：{secret_term_date}"
    else:
        term_display = f"解密条件：{secret_term_condition}"
    
    basis = classification_basis.get(basis_id, None)
    classification_records.append({
        'file_name': filename,
        'operator': session['username'],
        'basis_id': basis_id,
        'old_level': -1,
        'new_level': level,
        'reason': f"依据：{basis.basis_name if basis else '未知'}",
        'secret_term': term_display,
        'know_scope': know_scope,
        'know_persons': know_persons,
        'know_departments': know_departments,
        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    quick_save_file()
    add_audit_log(session['username'], "文件定密", filename, "成功", f"密级:{level}, 保密期限:{term_display}, 知悉范围:{know_scope[:50] if know_scope else '无'}")
    
    return jsonify({'success': True, 'message': f'定密成功，文件定为{get_level_name(level)}，保密期限：{term_display}'})

@app.route('/api/files/change', methods=['POST'])
@login_required
def change_classification():
    data = request.json
    filename = data.get('filename')
    new_level = data.get('new_level')
    basis_id = data.get('basis_id')
    
    file_found = None
    for i, d in document.items():
        if d.name == filename:
            file_found = i
            break
    
    if file_found is None:
        return jsonify({'success': False, 'message': '文件不存在'})
    if document[file_found].clearanceLevel > staff[session['user_id']].clearance:
        return jsonify({'success': False, 'message': '权限不足'})
    if document[file_found].clearanceLevel == -1:
        return jsonify({'success': False, 'message': '文件尚未定密'})
    if new_level == document[file_found].clearanceLevel:
        return jsonify({'success': False, 'message': '不能变更为相同密级'})
    if new_level > staff[session['user_id']].clearance:
        return jsonify({'success': False, 'message': '目标密级超出权限'})
    
    old_level = document[file_found].clearanceLevel
    document[file_found].clearanceLevel = new_level
    document[file_found].expirationDate = get_current_date()
    document[file_found].handledBy = session['user_id']
    
    from_path = get_clearance_path(old_level) + filename + ".txt"
    to_path = get_clearance_path(new_level) + filename + ".txt"
    if os.path.exists(from_path):
        shutil.copy2(from_path, to_path)
        os.remove(from_path)
    
    basis = classification_basis.get(basis_id, None)
    quick_save_file()
    add_audit_log(session['username'], "密级变更", filename, "成功", f"{get_level_name(old_level)} -> {get_level_name(new_level)}")
    
    return jsonify({'success': True, 'message': f'密级变更成功，新密级：{get_level_name(new_level)}'})

@app.route('/api/files/delete', methods=['POST'])
@admin_required
def delete_file():
    data = request.json
    filename = data.get('filename')
    
    file_id = None
    for i, d in document.items():
        if d.name == filename:
            file_id = i
            break
    
    if file_id is None:
        return jsonify({'success': False, 'message': '文件不存在'})
    
    file_found = document[file_id]
    if file_found.clearanceLevel == -1:
        file_path = DIRS['unknown'] + filename + ".txt"
    else:
        file_path = get_clearance_path(file_found.clearanceLevel) + filename + ".txt"
    
    if os.path.exists(file_path):
        os.remove(file_path)
    
    del document[file_id]
    
    if filename in secret_points:
        del secret_points[filename]
        with open("SecretPoints.txt", "w", encoding='utf-8') as f:
            for fn, pts in secret_points.items():
                for pt in pts:
                    f.write(f"{fn}|{pt['content']}|{pt['level']}|{pt['location']}\n")
    
    quick_save_file()
    add_audit_log(session['username'], "删除文件", filename, "成功", "")
    
    return jsonify({'success': True, 'message': f'文件 {filename} 删除成功'})

@app.route('/api/files/content', methods=['POST'])
@login_required
def get_file_content():
    data = request.json
    filename = data.get('filename')
    
    file_found = None
    for i, d in document.items():
        if d.name == filename:
            file_found = d
            break
    
    if file_found is None:
        return jsonify({'success': False, 'message': '文件不存在'})
    
    if file_found.clearanceLevel > staff[session['user_id']].clearance:
        return jsonify({'success': False, 'message': '权限不足'})
    
    if file_found.clearanceLevel == -1:
        file_path = DIRS['unknown'] + filename + ".txt"
    else:
        file_path = get_clearance_path(file_found.clearanceLevel) + filename + ".txt"
    
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'message': '文件不存在'})
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    return jsonify({'success': True, 'content': content})

@app.route('/api/files/secret-points/<filename>', methods=['GET'])
@login_required
def get_secret_points(filename):
    points = secret_points.get(filename, [])
    return jsonify({'success': True, 'points': points})

@app.route('/api/files/secret-points/add', methods=['POST'])
@login_required
def add_secret_point_api():
    data = request.json
    filename = data.get('filename')
    content = data.get('content')
    level = data.get('level')
    location = data.get('location', '未标注位置')
    
    if filename not in secret_points:
        secret_points[filename] = []
    secret_points[filename].append({'content': content, 'level': level, 'location': location})
    
    with open("SecretPoints.txt", "w", encoding='utf-8') as f:
        for fn, pts in secret_points.items():
            for pt in pts:
                f.write(f"{fn}|{pt['content']}|{pt['level']}|{pt['location']}\n")
    
    add_audit_log(session['username'], "标注密点", filename, "成功", f"密点:{content[:30]}")
    
    return jsonify({'success': True, 'message': '密点标注成功'})

@app.route('/api/ai/analyze', methods=['POST'])
@login_required
def ai_analyze():
    try:
        data = request.json
        filename = data.get('filename')
        
        file_found = None
        for i, d in document.items():
            if d.name == filename:
                file_found = d
                break
        
        if file_found is None:
            return jsonify({'success': False, 'message': '文件不存在'})
        
        if file_found.clearanceLevel == -1:
            file_path = DIRS['unknown'] + filename + ".txt"
        else:
            file_path = get_clearance_path(file_found.clearanceLevel) + filename + ".txt"
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'message': '文件不存在'})
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        if not content.strip():
            return jsonify({'success': False, 'message': '文件内容为空'})
        
        detected_points = ai_detect_sensitive(content)
        
        max_level = 0
        for point in detected_points:
            if point['level'] > max_level:
                max_level = point['level']
        
        if max_level == 3:
            reason = "检测到绝密级关键词或敏感信息"
        elif max_level == 2:
            reason = "检测到机密级关键词或敏感信息"
        elif max_level == 1:
            reason = "检测到秘密级关键词或敏感信息"
        else:
            reason = "未检测到明显敏感信息"
        
        lines = content.split('\n')
        density = len(detected_points) / max(len(lines), 1)
        
        return jsonify({
            'success': True,
            'content_length': len(content),
            'recommended_level': max_level,
            'recommended_level_name': get_level_name(max_level),
            'reason': reason,
            'detected_points': detected_points[:20],
            'density': round(density, 4),
            'total_points': len(detected_points)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'分析失败: {str(e)}'})

@app.route('/api/ai/auto-classify', methods=['POST'])
@login_required
def ai_auto_classify():
    data = request.json
    filename = data.get('filename')
    level = data.get('level')
    basis_id = data.get('basis_id')
    points = data.get('points', [])
    
    file_found = None
    for i, d in document.items():
        if d.name == filename:
            file_found = i
            break
    
    if file_found is None:
        return jsonify({'success': False, 'message': '文件不存在'})
    
    for point in points:
        if filename not in secret_points:
            secret_points[filename] = []
        existing = False
        for ep in secret_points[filename]:
            if ep['content'] == point['content']:
                existing = True
                break
        if not existing:
            secret_points[filename].append({
                'content': point['content'], 
                'level': point['level'], 
                'location': point.get('location', 'AI自动标注')
            })
    
    with open("SecretPoints.txt", "w", encoding='utf-8') as f:
        for fn, pts in secret_points.items():
            for pt in pts:
                f.write(f"{fn}|{pt['content']}|{pt['level']}|{pt['location']}\n")
    
    if document[file_found].clearanceLevel == -1 and level > 0:
        document[file_found].clearanceLevel = level
        document[file_found].expirationDate = get_current_date()
        document[file_found].handledBy = session['user_id']
        document[file_found].secret_term_type = '年限'
        document[file_found].secret_term_years = 5
        
        from_path = DIRS['unknown'] + filename + ".txt"
        to_path = get_clearance_path(level) + filename + ".txt"
        if os.path.exists(from_path):
            shutil.copy2(from_path, to_path)
            os.remove(from_path)
        
        quick_save_file()
        add_audit_log(session['username'], "AI辅助定密", filename, "成功", f"AI推荐密级:{get_level_name(level)}")
        message = f'已自动定密为{get_level_name(level)}，并标注{len(points)}个密点'
    else:
        message = f'已标注{len(points)}个密点'
    
    return jsonify({'success': True, 'message': message})

@app.route('/api/audit-logs', methods=['GET'])
@login_required
def get_audit_logs():
    return jsonify({'success': True, 'logs': audit_logs[-50:]})

@app.route('/api/basis-list', methods=['GET'])
@login_required
def get_basis_list():
    basis_list = [{'id': bid, 'name': b.basis_name, 'content': b.basis_content} for bid, b in classification_basis.items()]
    return jsonify({'success': True, 'basis': basis_list})

@app.route('/api/staff', methods=['GET'])
@login_required  # 改为仅需登录，不需要管理员
def get_staff():
    staff_list = []
    for i, s in staff.items():
        staff_list.append({
            'id': i,
            'username': s.username,
            'clearance': get_level_name(s.clearance),
            'clearance_level': s.clearance,
            'is_admin': s.isAdmin
        })
    return jsonify({'success': True, 'staff': staff_list})

@app.route('/api/staff/add', methods=['POST'])
@admin_required
def add_staff():
    global staffCount
    data = request.json
    username = data.get('username')
    password = data.get('password')
    clearance = data.get('clearance')
    
    staffCount += 1
    staff[staffCount] = type('obj', (object,), {'isAdmin': 0, 'username': username, 'passcode': password, 'clearance': clearance, 'originalClearance': clearance, 'authorizedBy': 0})
    
    quick_save_person()
    add_audit_log(session['username'], "添加人员", username, "成功", f"密级:{clearance}")
    
    return jsonify({'success': True, 'message': f'人员 {username} 添加成功'})

@app.route('/api/officers', methods=['GET'])
@login_required
def get_officers():
    officers = []
    if os.path.exists("ClassificationOfficers.txt"):
        with open("ClassificationOfficers.txt", "r", encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 6:
                    officers.append({
                        'id': int(parts[0]),
                        'name': parts[1],
                        'position': parts[2],
                        'appoint_date': parts[3],
                        'responsibility': parts[4],
                        'max_level': int(parts[5])
                    })
    return jsonify({'success': True, 'officers': officers})

@app.route('/api/officers/add', methods=['POST'])
@admin_required
def add_officer():
    data = request.json
    name = data.get('name')
    position = data.get('position')
    responsibility = data.get('responsibility', '')
    max_level = data.get('max_level', 3)
    
    if not name or not position:
        return jsonify({'success': False, 'message': '姓名和职务不能为空'})
    
    officer_id = 1
    if os.path.exists("ClassificationOfficers.txt"):
        with open("ClassificationOfficers.txt", "r", encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 1:
                    try:
                        oid = int(parts[0])
                        if oid >= officer_id:
                            officer_id = oid + 1
                    except:
                        pass
    
    appoint_date = datetime.now().strftime("%Y-%m-%d")
    
    with open("ClassificationOfficers.txt", "a", encoding='utf-8') as f:
        f.write(f"{officer_id}|{name}|{position}|{appoint_date}|{responsibility}|{max_level}\n")
    
    add_audit_log(session['username'], "添加定密责任人", name, "成功", f"职务:{position},权限:{max_level}")
    
    return jsonify({'success': True, 'message': f'定密责任人 {name} 添加成功'})

@app.route('/api/officers/delete/<int:officer_id>', methods=['DELETE'])
@admin_required
def delete_officer(officer_id):
    if not os.path.exists("ClassificationOfficers.txt"):
        return jsonify({'success': False, 'message': '没有定密责任人记录'})
    
    lines = []
    deleted = False
    with open("ClassificationOfficers.txt", "r", encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('|')
            if len(parts) >= 1 and int(parts[0]) != officer_id:
                lines.append(line)
            else:
                deleted = True
    
    with open("ClassificationOfficers.txt", "w", encoding='utf-8') as f:
        f.writelines(lines)
    
    if deleted:
        add_audit_log(session['username'], "删除定密责任人", str(officer_id), "成功", "")
        return jsonify({'success': True, 'message': '删除成功'})
    else:
        return jsonify({'success': False, 'message': '未找到该责任人'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)