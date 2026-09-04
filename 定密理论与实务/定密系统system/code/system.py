import os
import shutil
import time
import json
import re
from datetime import datetime
from typing import List, Dict, Optional

# AI相关导入
try:
    from aip import AipNlp
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("警告：未安装baidu-aip库，AI功能将受限。请运行: pip install baidu-aip")

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


# ==================== AI配置 ====================

BAIDU_APP_ID = "20260520002616845"
BAIDU_API_KEY = "JrUW_d8ietju7s844c8bc3lv0"
BAIDU_SECRET_KEY = "MQGtX5E1x3HvQnAEHumJ"
USE_BAIDU_AI = True

# 敏感词库（用于AI识别密点）
SENSITIVE_KEYWORDS = {
    "绝密": [
        "核武器", "导弹", "军事部署", "情报来源", "密码算法", "领导人行程",
        "核弹头", "战略武器", "国防动员", "战争计划", "核设施"
    ],
    "机密": [
        "国防预算", "武器装备", "作战计划", "外交谈判", "经济数据",
        "军事基地", "部队调动", "情报人员", "反恐行动", "网络安全"
    ],
    "秘密": [
        "内部会议", "人事任免", "项目进展", "技术参数", "合同细节",
        "内部文件", "工作方案", "调查报告", "审计报告", "应急预案"
    ]
}

# 行业关键词
INDUSTRY_KEYWORDS = {
    "军事": ["部队", "武器", "导弹", "雷达", "卫星", "国防", "军演", "弹药"],
    "政治": ["决策", "政策", "领导人", "会议", "文件", "批示", "指示"],
    "经济": ["GDP", "财政", "预算", "投资", "金融", "税收", "国债"],
    "科技": ["专利", "技术", "研发", "芯片", "算法", "源代码", "核心技术"]
}


# ==================== 类定义 ====================

# 定义人员类
class Staff:
    def __init__(self, isAdmin, username, passcode, clearance, originalClearance, authorizedBy):
        self.isAdmin = isAdmin
        self.username = username
        self.passcode = passcode
        self.clearance = clearance
        self.originalClearance = originalClearance
        self.authorizedBy = authorizedBy

# 定义文件类
class Document:
    def __init__(self, name, clearanceLevel, expirationDate, handledBy, accessKey, expirationYear=0):
        self.name = name
        self.clearanceLevel = clearanceLevel
        self.expirationDate = expirationDate
        self.expirationYear = expirationYear
        self.handledBy = handledBy
        self.accessKey = accessKey

# 定密依据类
class ClassificationBasis:
    def __init__(self, basis_id: str, basis_name: str, basis_content: str, basis_type: str = ""):
        self.basis_id = basis_id
        self.basis_name = basis_name
        self.basis_content = basis_content
        self.basis_type = basis_type

# 定密责任人
class ClassificationOfficer:
    def __init__(self, officer_id: int, name: str, position: str, 
                 appoint_date: str, responsibility: str, max_level: int = 3):
        self.officer_id = officer_id
        self.name = name
        self.position = position
        self.appoint_date = appoint_date
        self.responsibility = responsibility
        self.max_level = max_level

# 审计日志
class AuditLog:
    def __init__(self, operator: str, operation_type: str, 
                 target_name: str, result: str, details: str = ""):
        self.operation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.operator = operator
        self.operation_type = operation_type
        self.target_name = target_name
        self.result = result
        self.details = details

# 密点信息
class SecretPoint:
    def __init__(self, file_name: str, point_content: str, 
                 point_level: int, location: str = ""):
        self.file_name = file_name
        self.point_content = point_content
        self.point_level = point_level
        self.location = location

# 定密流程记录
class ClassificationRecord:
    def __init__(self, file_name: str, operator: str, basis_id: str,
                 old_level: int, new_level: int, reason: str = ""):
        self.file_name = file_name
        self.operator = operator
        self.basis_id = basis_id
        self.old_level = old_level
        self.new_level = new_level
        self.reason = reason
        self.operation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ==================== 全局变量 ====================

staff = {}
document = {}
staffCount = 0
documentCount = 0

classification_basis: Dict[str, ClassificationBasis] = {}
classification_officers: Dict[int, ClassificationOfficer] = {}
audit_logs: List[AuditLog] = []
secret_points: Dict[str, List[SecretPoint]] = {}
classification_records: List[ClassificationRecord] = []
officer_count = 0

# 文件夹路径
DIRS = {
    'unknown': './Unknown/',
    'secret': './Secret/',
    'confidential': './Confidential/',
    'topsecret': './Top-secret/',
    'unclassified': './Unclassified/',
    'use': './Use/'
}


# ==================== 基础功能函数 ====================

def create_directories():
    for dir_path in DIRS.values():
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

def get_current_date():
    now = datetime.now()
    return now.year * 10000 + now.month * 100 + now.day

def get_current_date_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_clearance_path(clearance_level):
    if clearance_level == 1:
        return DIRS['secret']
    elif clearance_level == 2:
        return DIRS['confidential']
    elif clearance_level == 3:
        return DIRS['topsecret']
    return DIRS['unknown']

def get_level_name(level):
    return {0: "非密", 1: "秘密", 2: "机密", 3: "绝密", -1: "未定密"}.get(level, "未知")


# ==================== 快速保存模块 ====================

def quick_save_person():
    """立即保存人员数据到Person.txt"""
    with open("Person.txt", "w", encoding='utf-8') as f:
        f.write(f"{staffCount}\n")
        for i in range(1, staffCount + 1):
            s = staff[i]
            f.write(f"{s.isAdmin} {s.username} {s.passcode} {s.clearance} {s.originalClearance} {s.authorizedBy}\n")

def quick_save_file():
    """立即保存文件数据到File.txt"""
    with open("File.txt", "w", encoding='utf-8') as f:
        f.write(f"{documentCount}\n")
        for i in range(1, documentCount + 1):
            d = document[i]
            f.write(f"{d.name} {d.clearanceLevel} {d.expirationDate} {d.handledBy} {d.accessKey} {d.expirationYear}\n")


# ==================== 定密依据模块 ====================

def init_classification_basis():
    """初始化定密依据库（基于《保密法》及其实施条例）"""
    global classification_basis
    basis_data = [
        # ========== 《中华人民共和国保守国家秘密法》 ==========
        ("B001", "《保密法》第十三条", 
         "下列涉及国家安全和利益的事项，泄露后可能损害国家在政治、经济、国防、外交等领域的安全和利益的，应当确定为国家秘密：\n"
         "（一）国家事务重大决策中的秘密事项；\n"
         "（二）国防建设和武装力量活动中的秘密事项；\n"
         "（三）外交和外事活动中的秘密事项以及对外承担保密义务的秘密事项；\n"
         "（四）国民经济和社会发展中的秘密事项；\n"
         "（五）科学技术中的秘密事项；\n"
         "（六）维护国家安全活动和追查刑事犯罪中的秘密事项；\n"
         "（七）经国家保密行政管理部门确定的其他秘密事项。\n"
         "政党的秘密事项中符合前款规定的，属于国家秘密。", "法律"),
        
        ("B002", "《保密法》第十四条", 
         "国家秘密的密级分为绝密、机密、秘密三级。\n"
         "绝密级国家秘密是最重要的国家秘密，泄露会使国家安全和利益遭受特别严重的损害；\n"
         "机密级国家秘密是重要的国家秘密，泄露会使国家安全和利益遭受严重的损害；\n"
         "秘密级国家秘密是一般的国家秘密，泄露会使国家安全和利益遭受损害。", "法律"),
        
        ("B003", "《保密法》第十五条", 
         "国家秘密及其密级的具体范围（以下简称保密事项范围），由国家保密行政管理部门单独或者会同有关中央国家机关规定。\n"
         "军事方面的保密事项范围，由中央军事委员会规定。\n"
         "保密事项范围的确定应当遵循必要、合理原则，科学论证评估，并根据情况变化及时调整。", "法律"),
        
        ("B004", "《保密法》第十六条", 
         "机关、单位主要负责人及其指定的人员为定密责任人，负责本机关、本单位的国家秘密确定、变更和解除工作。\n"
         "机关、单位确定、变更和解除本机关、本单位的国家秘密，应当由承办人提出具体意见，经定密责任人审核批准。", "法律"),
        
        ("B005", "《保密法》第十七条", 
         "确定国家秘密的密级，应当遵守定密权限。\n"
         "中央国家机关、省级机关及其授权的机关、单位可以确定绝密级、机密级和秘密级国家秘密；\n"
         "设区的市级机关及其授权的机关、单位可以确定机密级和秘密级国家秘密。\n"
         "下级机关、单位认为本机关、本单位产生的有关定密事项属于上级机关、单位的定密权限，应当先行采取保密措施，并立即报请上级机关、单位确定。", "法律"),
        
        ("B006", "《保密法》第二十条", 
         "国家秘密的保密期限，应当根据事项的性质和特点，按照维护国家安全和利益的需要，限定在必要的期限内。\n"
         "国家秘密的保密期限，除另有规定外，绝密级不超过三十年，机密级不超过二十年，秘密级不超过十年。\n"
         "机关、单位应当根据工作需要，确定具体的保密期限、解密时间或者解密条件。", "法律"),
        
        ("B007", "《保密法》第二十一条", 
         "国家秘密的知悉范围，应当根据工作需要限定在最小范围。\n"
         "国家秘密的知悉范围能够限定到具体人员的，限定到具体人员；不能限定到具体人员的，限定到机关、单位。\n"
         "国家秘密的知悉范围以外的人员，因工作需要知悉国家秘密的，应当经过机关、单位主要负责人或者其指定的人员批准。", "法律"),
        
        ("B008", "《保密法》第二十二条", 
         "机关、单位对承载国家秘密的纸介质、光介质、电磁介质等载体以及属于国家秘密的设备、产品，应当作出国家秘密标志。\n"
         "涉及国家秘密的电子文件应当按照国家有关规定作出国家秘密标志。\n"
         "不属于国家秘密的，不得作出国家秘密标志。", "法律"),
        
        ("B009", "《保密法》第二十三条", 
         "国家秘密的密级、保密期限和知悉范围，应当根据情况变化及时变更。\n"
         "国家秘密的密级、保密期限和知悉范围的变更，由原定密机关、单位决定，也可以由其上级机关决定。\n"
         "国家秘密的密级、保密期限和知悉范围变更的，应当及时书面通知知悉范围内的机关、单位或者人员。", "法律"),
        
        ("B010", "《保密法》第二十四条", 
         "机关、单位应当每年审核所确定的国家秘密。\n"
         "国家秘密的保密期限已满的，自行解密。\n"
         "在保密期限内因保密事项范围调整不再作为国家秘密，或者公开后不会损害国家安全和利益，不需要继续保密的，应当及时解密。", "法律"),
        
        # ========== 《保密法实施条例》 ==========
        ("C001", "《保密法实施条例》第十二条", 
         "国家秘密及其密级的具体范围应当明确规定国家秘密具体事项的名称、密级、保密期限、知悉范围和产生层级。\n"
         "保密事项范围应当根据情况变化及时调整。制定、修订保密事项范围应当充分论证，听取有关机关、单位和相关行业、领域专家的意见。", "行政法规"),
        
        ("C002", "《保密法实施条例》第十四条", 
         "机关、单位主要负责人为本机关、本单位法定定密责任人，根据工作需要，可以明确本机关、本单位其他负责人、内设机构负责人或者其他人员为指定定密责任人。\n"
         "定密责任人、承办人应当接受定密培训，熟悉定密职责和保密事项范围，掌握定密程序和方法。", "行政法规"),
        
        ("C003", "《保密法实施条例》第十五条", 
         "定密责任人在职责范围内承担国家秘密确定、变更和解除工作，指导、监督职责范围内的定密工作。具体职责是：\n"
         "（一）审核批准承办人拟定的国家秘密的密级、保密期限和知悉范围；\n"
         "（二）对本机关、本单位确定的尚在保密期限内的国家秘密进行审核，作出是否变更或者解除的决定；\n"
         "（三）参与制定修订本机关、本单位国家秘密事项一览表；\n"
         "（四）对是否属于国家秘密和属于何种密级不明确的事项先行拟定密级、保密期限和知悉范围，并按照规定的程序报保密行政管理部门确定。", "行政法规"),
        
        ("C004", "《保密法实施条例》第十六条", 
         "中央国家机关、省级机关以及设区的市级机关可以根据保密工作需要或者有关机关、单位申请，在国家保密行政管理部门规定的定密权限、授权范围内作出定密授权。\n"
         "定密授权应当以书面形式作出。授权机关应当对被授权机关、单位履行定密授权的情况进行监督。被授权机关、单位不得再授权。", "行政法规"),
        
        ("C005", "《保密法实施条例》第十七条", 
         "机关、单位应当在国家秘密产生的同时，由承办人依据有关保密事项范围拟定密级、保密期限和知悉范围，报定密责任人审核批准，并采取相应保密措施。\n"
         "机关、单位确定国家秘密，能够明确密点的，按照国家保密规定确定并标注。", "行政法规"),
        
        ("C006", "《保密法实施条例》第十九条", 
         "机关、单位对所产生的国家秘密，应当按照保密事项范围的规定确定具体的保密期限或者解密时间；不能确定的，应当确定解密条件。\n"
         "国家秘密的保密期限，自标明的制发日起计算；不能标明制发日的，确定该国家秘密的机关、单位应当书面通知知悉范围内的机关、单位和人员，保密期限自通知之日起计算。", "行政法规"),
        
        ("C007", "《保密法实施条例》第二十条", 
         "机关、单位应当依法限定国家秘密的知悉范围，对知悉机密级以上国家秘密的人员，应当作出记录。", "行政法规"),
        
        ("C008", "《保密法实施条例》第二十一条", 
         "国家秘密载体以及属于国家秘密的设备、产品的明显部位应当作出国家秘密标志。国家秘密标志应当标注密级、保密期限。\n"
         "国家秘密的密级或者保密期限发生变更的，应当及时对原国家秘密标志作出变更。", "行政法规"),
        
        ("C009", "《保密法实施条例》第二十二条", 
         "机关、单位对所确定的国家秘密，认为符合保密法有关解除或者变更规定的，应当及时解除或者变更。\n"
         "机关、单位对不属于本机关、本单位确定的国家秘密，认为符合保密法有关解除或者变更规定的，可以向原定密机关、单位或者其上级机关、单位提出建议。", "行政法规"),
        
        ("C010", "《保密法实施条例》第二十四条", 
         "机关、单位发现本机关、本单位国家秘密的确定、变更和解除不当的，应当及时纠正；\n"
         "上级机关、单位发现下级机关、单位国家秘密的确定、变更和解除不当的，应当及时通知其纠正，也可以直接纠正。", "行政法规"),
        
        ("C011", "《保密法实施条例》第二十五条", 
         "机关、单位对符合保密法的规定，但保密事项范围没有规定的不明确事项，应当先行拟定密级、保密期限和知悉范围，采取相应的保密措施，并自拟定之日起10个工作日内报有关部门确定。", "行政法规"),
    ]
    
    for data in basis_data:
        classification_basis[data[0]] = ClassificationBasis(
            data[0], data[1], data[2], data[3]
        )
    
    print(f"✓ 已加载 {len(classification_basis)} 条定密依据（含《保密法》及其实施条例）")

def show_basis_list():
    basis_list = list(classification_basis.values())
    for i, basis in enumerate(basis_list, 1):
        print(f"  {i}. {basis.basis_name}")
    return basis_list

def select_classification_basis():
    basis_list = list(classification_basis.values())
    print("\n请选择定密依据：")
    for i, basis in enumerate(basis_list, 1):
        print(f"  {i}. {basis.basis_name}")
    print("  0. 自定义依据")
    
    choice = input("请输入编号：")
    if choice == '0':
        basis_name = input("请输入定密依据名称：")
        basis_content = input("请输入定密依据内容：")
        basis_id = f"CUSTOM_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        classification_basis[basis_id] = ClassificationBasis(
            basis_id, basis_name, basis_content, "自定义"
        )
        return classification_basis[basis_id]
    elif choice.isdigit() and 1 <= int(choice) <= len(basis_list):
        return basis_list[int(choice) - 1]
    else:
        print("输入无效，使用默认依据")
        return basis_list[0] if basis_list else None


# ==================== 审计日志模块 ====================

def add_audit_log(operator: str, operation_type: str, 
                  target_name: str, result: str, details: str = ""):
    log = AuditLog(operator, operation_type, target_name, result, details)
    audit_logs.append(log)
    save_audit_logs()

def save_audit_logs():
    with open("AuditLog.txt", "w", encoding='utf-8') as f:
        for log in audit_logs:
            f.write(f"{log.operation_time}|{log.operator}|{log.operation_type}|"
                    f"{log.target_name}|{log.result}|{log.details}\n")

def load_audit_logs():
    global audit_logs
    audit_logs = []
    if os.path.exists("AuditLog.txt"):
        with open("AuditLog.txt", "r", encoding='utf-8') as f:
            for line in f.readlines():
                parts = line.strip().split('|')
                if len(parts) >= 5:
                    log = AuditLog(parts[1], parts[2], parts[3], parts[4], 
                                   parts[5] if len(parts) > 5 else "")
                    log.operation_time = parts[0]
                    audit_logs.append(log)

def view_audit_logs():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 70)
    print("                        审计日志")
    print("=" * 70)
    print(f"{'时间':<20} {'操作人':<12} {'操作类型':<12} {'目标':<15} {'结果':<6}")
    print("-" * 70)
    for log in audit_logs[-50:]:
        print(f"{log.operation_time:<20} {log.operator:<12} {log.operation_type:<12} "
              f"{log.target_name:<15} {log.result:<6}")
    print("-" * 70)
    if len(audit_logs) > 50:
        print(f"共{len(audit_logs)}条记录，仅显示最近50条")
    input("\n按回车键继续...")


# ==================== 定密责任人模块 ====================

def add_classification_officer():
    global officer_count, classification_officers
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 50)
    print("          添加定密责任人")
    print("=" * 50)
    
    officer_count += 1
    name = input("请输入责任人姓名：")
    position = input("请输入责任人职务：")
    appoint_date = get_current_date_str()
    responsibility = input("请输入职责范围：")
    max_level = input("请输入最高定密权限（1：秘密，2：机密，3：绝密）：")
    while max_level not in ['1', '2', '3']:
        max_level = input("输入错误，请重新输入：")
    
    classification_officers[officer_count] = ClassificationOfficer(
        officer_count, name, position, appoint_date, responsibility, int(max_level)
    )
    
    print(f"\n定密责任人 {name} 添加成功！")
    add_audit_log("系统", "添加定密责任人", name, "成功", f"职务:{position}")
    save_classification_officers()
    time.sleep(1)

def save_classification_officers():
    with open("ClassificationOfficers.txt", "w", encoding='utf-8') as f:
        for officer in classification_officers.values():
            f.write(f"{officer.officer_id}|{officer.name}|{officer.position}|"
                    f"{officer.appoint_date}|{officer.responsibility}|{officer.max_level}\n")

def load_classification_officers():
    global officer_count, classification_officers
    classification_officers = {}
    officer_count = 0
    if os.path.exists("ClassificationOfficers.txt"):
        with open("ClassificationOfficers.txt", "r", encoding='utf-8') as f:
            for line in f.readlines():
                parts = line.strip().split('|')
                if len(parts) >= 6:
                    officer_count += 1
                    classification_officers[int(parts[0])] = ClassificationOfficer(
                        int(parts[0]), parts[1], parts[2], parts[3], parts[4], int(parts[5])
                    )

def view_classification_officers():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 80)
    print("                    定密责任人列表")
    print("=" * 80)
    print(f"{'ID':<4} {'姓名':<10} {'职务':<15} {'任命日期':<12} {'职责范围':<20} {'最高密级':<8}")
    print("-" * 80)
    for officer in classification_officers.values():
        level_name = get_level_name(officer.max_level)
        print(f"{officer.officer_id:<4} {officer.name:<10} {officer.position:<15} "
              f"{officer.appoint_date:<12} {officer.responsibility:<20} {level_name:<8}")
    print("-" * 80)
    input("按回车键继续...")


# ==================== 密点标注模块 ====================

def add_secret_point(file_name: str, operator: str):
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 60)
    print(f"    为文件《{file_name}》标注密点")
    print("=" * 60)
    print("提示：密点是指文件中涉及国家秘密的具体内容")
    print("-" * 60)
    
    while True:
        point_content = input("\n请输入密点内容（输入q退出）：")
        if point_content.lower() == 'q':
            break
        
        if not point_content.strip():
            print("密点内容不能为空！")
            continue
        
        point_level = input("请输入该密点的密级（1：秘密，2：机密，3：绝密）：")
        while point_level not in ['1', '2', '3']:
            point_level = input("输入错误，请重新输入（1-3）：")
        
        location = input("请输入密点位置（如：第3页第2段）：")
        if not location:
            location = "未标注位置"
        
        if file_name not in secret_points:
            secret_points[file_name] = []
        
        secret_points[file_name].append(SecretPoint(
            file_name, point_content, int(point_level), location
        ))
        print(f"✓ 密点标注成功！当前文件已有 {len(secret_points[file_name])} 个密点")
        add_audit_log(operator, "标注密点", file_name, "成功", f"密点:{point_content[:30]}")
        save_secret_points()
    
    print("\n密点标注完成！")
    time.sleep(1)

def view_secret_points(file_name: str):
    if file_name in secret_points and secret_points[file_name]:
        print(f"\n文件《{file_name}》的密点标注：")
        print("-" * 50)
        for i, point in enumerate(secret_points[file_name], 1):
            level_name = get_level_name(point.point_level)
            print(f"{i}. 密点内容：{point.point_content}")
            print(f"   密级：{level_name}  位置：{point.location}\n")
    else:
        print("该文件暂无密点标注")

def view_all_secret_points():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 60)
    print("                所有密点标注")
    print("=" * 60)
    
    if not secret_points:
        print("暂无任何密点标注")
    else:
        for file_name, points in secret_points.items():
            print(f"\n【文件：{file_name}】")
            print("-" * 40)
            for i, point in enumerate(points, 1):
                level_name = get_level_name(point.point_level)
                print(f"  {i}. {point.point_content}")
                print(f"     密级：{level_name}  位置：{point.location}")
    
    print("\n" + "=" * 60)
    input("按回车键继续...")

def save_secret_points():
    with open("SecretPoints.txt", "w", encoding='utf-8') as f:
        for file_name, points in secret_points.items():
            for point in points:
                f.write(f"{file_name}|{point.point_content}|{point.point_level}|{point.location}\n")

def load_secret_points():
    global secret_points
    secret_points = {}
    if os.path.exists("SecretPoints.txt"):
        with open("SecretPoints.txt", "r", encoding='utf-8') as f:
            for line in f.readlines():
                parts = line.strip().split('|')
                if len(parts) >= 3:
                    file_name = parts[0]
                    point = SecretPoint(file_name, parts[1], int(parts[2]), 
                                        parts[3] if len(parts) > 3 else "")
                    if file_name not in secret_points:
                        secret_points[file_name] = []
                    secret_points[file_name].append(point)


# ==================== AI密点识别模块 ====================

def init_baidu_ai():
    """初始化百度AI客户端"""
    if not AI_AVAILABLE:
        return None
    try:
        if BAIDU_API_KEY != "JrUW_d8ietju7s844c8bc3lv0" and BAIDU_SECRET_KEY != "MQGtX5E1x3HvQnAEHumJ":
            client = AipNlp(BAIDU_APP_ID, BAIDU_API_KEY, BAIDU_SECRET_KEY)
            return client
        else:
            print("⚠️ 请先配置百度AI的API Key和Secret Key")
            return None
    except Exception as e:
        print(f"百度AI初始化失败：{e}")
        return None

def read_file_content(file_path: str) -> str:
    """读取文件内容（支持txt、docx、pdf）"""
    content = ""
    try:
        if file_path.endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        
        elif file_path.endswith('.docx') and DOCX_AVAILABLE:
            doc = docx.Document(file_path)
            content = '\n'.join([para.text for para in doc.paragraphs])
        
        elif file_path.endswith('.pdf') and PDF_AVAILABLE:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    content += page.extract_text()
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
    except Exception as e:
        print(f"读取文件失败：{e}")
        content = ""
    
    return content

def keyword_based_detection(content: str) -> List[tuple]:
    """基于关键词的敏感信息识别"""
    detected_points = []
    lines = content.split('\n')
    
    for line_num, line in enumerate(lines, 1):
        if not line.strip():
            continue
        line_lower = line.lower()
        
        # 检查绝密级关键词
        for keyword in SENSITIVE_KEYWORDS["绝密"]:
            if keyword.lower() in line_lower:
                detected_points.append((line.strip()[:200], 3, f"第{line_num}行"))
                break
        else:
            # 检查机密级关键词
            for keyword in SENSITIVE_KEYWORDS["机密"]:
                if keyword.lower() in line_lower:
                    detected_points.append((line.strip()[:200], 2, f"第{line_num}行"))
                    break
            else:
                # 检查秘密级关键词
                for keyword in SENSITIVE_KEYWORDS["秘密"]:
                    if keyword.lower() in line_lower:
                        detected_points.append((line.strip()[:200], 1, f"第{line_num}行"))
                        break
        
        # 检查数字模式
        id_card_pattern = r'[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]'
        if re.search(id_card_pattern, line):
            detected_points.append((line.strip()[:200], 2, f"第{line_num}行 - 身份证号"))
        
        phone_pattern = r'1[3-9]\d{9}'
        if re.search(phone_pattern, line):
            detected_points.append((line.strip()[:200], 1, f"第{line_num}行 - 手机号"))
        
        money_pattern = r'[1-9]\d{6,}(?:万|亿)?'
        if re.search(money_pattern, line):
            detected_points.append((line.strip()[:200], 2, f"第{line_num}行 - 大额数字"))
    
    # 去重
    seen = set()
    unique_points = []
    for point in detected_points:
        if point[0] not in seen:
            seen.add(point[0])
            unique_points.append(point)
    
    return unique_points

def baidu_ai_detection(content: str, client) -> List[tuple]:
    """使用百度AI识别敏感信息"""
    detected_points = []
    
    if not client:
        return []
    
    try:
        # 限制长度避免超限
        content_sample = content[:1000]
        result = client.lexer(content_sample)
        if 'items' in result:
            for item in result['items']:
                word = item.get('word', '')
                pos = item.get('pos', '')
                if len(word) < 2:
                    continue
                # 识别专有名词
                if pos in ['nr', 'ns', 'nt']:
                    if pos == 'nt':  # 机构名
                        detected_points.append((word, 2, f"AI识别：机构名"))
                    elif pos == 'ns':  # 地名
                        detected_points.append((word, 1, f"AI识别：地名"))
                    elif pos == 'nr':  # 人名
                        detected_points.append((word, 1, f"AI识别：人名"))
    except Exception as e:
        print(f"AI识别出错：{e}")
    
    return detected_points

def suggest_classification_level(content: str, filename: str = "") -> dict:
    """分析文件内容，推荐定密密级"""
    print("\n🤖 AI正在分析文件内容...")
    
    keyword_points = keyword_based_detection(content)
    
    ai_points = []
    if USE_BAIDU_AI:
        client = init_baidu_ai()
        if client:
            ai_points = baidu_ai_detection(content, client)
    
    all_points = keyword_points + ai_points
    
    max_level = 0
    for _, level, _ in all_points:
        if level > max_level:
            max_level = level
    
    if "绝密" in filename or "top" in filename.lower():
        max_level = max(max_level, 3)
    elif "机密" in filename or "confidential" in filename.lower():
        max_level = max(max_level, 2)
    elif "秘密" in filename or "secret" in filename.lower():
        max_level = max(max_level, 1)
    
    if max_level == 3:
        reason = "检测到绝密级关键词或敏感信息，建议定密为【绝密】"
    elif max_level == 2:
        reason = "检测到机密级关键词或敏感信息，建议定密为【机密】"
    elif max_level == 1:
        reason = "检测到秘密级关键词或敏感信息，建议定密为【秘密】"
    else:
        reason = "未检测到明显敏感信息，建议定密为【非密】或进一步人工审核"
    
    return {
        "level": max_level,
        "reason": reason,
        "points": all_points,
        "has_sensitive": len(all_points) > 0
    }

def ai_assisted_secret_point(file_name: str, operator: str):
    """AI辅助密点标注"""
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 60)
    print("        🤖 AI辅助密点识别")
    print("=" * 60)
    
    file_found = None
    for i in range(1, documentCount + 1):
        if document[i].name == file_name:
            file_found = i
            break
    
    if file_found is None:
        print("✗ 文件不存在！")
        time.sleep(1)
        return
    
    if document[file_found].clearanceLevel == -1:
        file_path = DIRS['unknown'] + file_name + ".txt"
    else:
        file_path = get_clearance_path(document[file_found].clearanceLevel) + file_name + ".txt"
    
    if not os.path.exists(file_path):
        for ext in ['.txt', '.docx', '.pdf']:
            test_path = file_path.replace('.txt', ext)
            if os.path.exists(test_path):
                file_path = test_path
                break
    
    print(f"\n📄 正在分析文件：{file_name}")
    
    content = read_file_content(file_path)
    
    if not content:
        print("✗ 无法读取文件内容或文件为空")
        time.sleep(1)
        return
    
    print(f"✓ 文件读取成功，共 {len(content)} 字符")
    
    analysis = suggest_classification_level(content, file_name)
    
    print("\n" + "=" * 60)
    print("        📊 AI分析结果")
    print("=" * 60)
    
    level_name = get_level_name(analysis["level"])
    print(f"\n🔍 推荐定密密级：{level_name}")
    print(f"📝 推荐理由：{analysis['reason']}")
    
    if analysis["points"]:
        print(f"\n⚠️ 检测到 {len(analysis['points'])} 个可能密点：")
        print("-" * 50)
        for i, (point_text, level, location) in enumerate(analysis["points"][:10], 1):
            level_name_short = get_level_name(level)
            point_display = point_text[:50] + "..." if len(point_text) > 50 else point_text
            print(f"{i}. {point_display}")
            print(f"   建议密级：{level_name_short}  | 位置：{location}")
            print()
    else:
        print("\n✓ 未检测到明显敏感信息")
    
    print("-" * 60)
    print("\n请选择操作：")
    print("1. 采纳AI建议的密级并自动标注密点")
    print("2. 仅标注AI识别的密点（不修改密级）")
    print("3. 手动标注密点")
    print("4. 跳过")
    
    choice = input("\n请输入选择：")
    
    if choice == '1':
        if analysis["level"] > 0 and document[file_found].clearanceLevel != analysis["level"]:
            print(f"\n✓ 正在将文件密级调整为 {level_name}")
            
            if document[file_found].clearanceLevel == -1:
                document[file_found].clearanceLevel = analysis["level"]
                document[file_found].expirationYear = 5
                document[file_found].expirationDate = get_current_date()
                document[file_found].handledBy = [k for k, v in staff.items() if v.username == operator][0]
                
                from_path = DIRS['unknown'] + file_name + ".txt"
                to_path = get_clearance_path(analysis["level"]) + file_name + ".txt"
                if os.path.exists(from_path):
                    shutil.copy2(from_path, to_path)
                
                print(f"✓ 文件已定密为 {level_name}")
                add_audit_log(operator, "AI辅助定密", file_name, "成功", f"AI推荐密级:{level_name}")
            else:
                document[file_found].clearanceLevel = analysis["level"]
                add_audit_log(operator, "AI辅助密级变更", file_name, "成功", f"变更为:{level_name}")
        
        for point_text, level, location in analysis["points"]:
            if file_name not in secret_points:
                secret_points[file_name] = []
            secret_points[file_name].append(SecretPoint(
                file_name, point_text[:100], level, location
            ))
        save_secret_points()
        print(f"✓ 已自动标注 {len(analysis['points'])} 个密点")
        
    elif choice == '2':
        for point_text, level, location in analysis["points"]:
            if file_name not in secret_points:
                secret_points[file_name] = []
            secret_points[file_name].append(SecretPoint(
                file_name, point_text[:100], level, location
            ))
        save_secret_points()
        print(f"✓ 已标注 {len(analysis['points'])} 个密点")
        add_audit_log(operator, "AI辅助密点标注", file_name, "成功", f"标注{len(analysis['points'])}个密点")
        
    elif choice == '3':
        add_secret_point(file_name, operator)
    
    else:
        print("已跳过")
    
    print("\n按回车键继续...")
    input()

def batch_ai_analysis():
    """批量分析Unknown文件夹中的待定密文件"""
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 60)
    print("        🤖 批量AI文件分析")
    print("=" * 60)
    
    unknown_files = []
    for f in os.listdir(DIRS['unknown']):
        if f.endswith('.txt'):
            unknown_files.append(f.replace('.txt', ''))
    
    if not unknown_files:
        print("\nUnknown文件夹中没有待分析的文件")
        time.sleep(1)
        return
    
    print(f"\n发现 {len(unknown_files)} 个待分析文件：")
    for i, f in enumerate(unknown_files, 1):
        print(f"  {i}. {f}")
    
    print("\n开始批量分析...")
    print("-" * 40)
    
    results = []
    for filename in unknown_files:
        file_path = DIRS['unknown'] + filename + ".txt"
        content = read_file_content(file_path)
        analysis = suggest_classification_level(content, filename)
        results.append((filename, analysis))
        
        level_name = get_level_name(analysis["level"])
        print(f"📄 {filename}: 推荐 {level_name} ({len(analysis['points'])}个密点)")
    
    print("\n" + "=" * 60)
    print("批量分析完成！")
    print("\n是否将分析结果保存到报告文件？(y/n)")
    if input().lower() == 'y':
        with open("AIAnalysisReport.txt", "w", encoding='utf-8') as f:
            f.write("AI密点分析报告\n")
            f.write(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            for filename, analysis in results:
                f.write(f"文件：{filename}\n")
                f.write(f"推荐密级：{get_level_name(analysis['level'])}\n")
                f.write(f"推荐理由：{analysis['reason']}\n")
                f.write(f"检测密点数：{len(analysis['points'])}\n")
                f.write("-" * 40 + "\n")
        print("✓ 报告已保存到 AIAnalysisReport.txt")
    
    input("\n按回车键继续...")


# ==================== 定密监督模块 ====================

def view_classification_records():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 90)
    print("                    定密流程记录")
    print("=" * 90)
    print(f"{'时间':<20} {'操作人':<10} {'文件':<12} {'原密级':<8} {'新密级':<8} {'定密依据':<25}")
    print("-" * 90)
    
    if not classification_records:
        print("暂无定密流程记录")
    else:
        for record in classification_records[-50:]:
            old_name = get_level_name(record.old_level)
            new_name = get_level_name(record.new_level)
            basis = classification_basis.get(record.basis_id)
            basis_name = basis.basis_name[:23] if basis else "未知依据"
            print(f"{record.operation_time:<20} {record.operator:<10} {record.file_name:<12} "
                  f"{old_name:<8} {new_name:<8} {basis_name:<25}")
    
    print("-" * 90)
    if len(classification_records) > 50:
        print(f"共{len(classification_records)}条记录，仅显示最近50条")
    input("\n按回车键继续...")

def supervision_interface():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 50)
        print("            定密监督")
        print("=" * 50)
        print("1. 查看定密流程记录")
        print("2. 查看审计日志")
        print("3. 查看定密责任人")
        print("4. 查看密点标注情况")
        print("5. 返回上级菜单")
        print("-" * 50)
        
        choice = input("请输入操作：")
        
        if choice == '1':
            view_classification_records()
        elif choice == '2':
            view_audit_logs()
        elif choice == '3':
            view_classification_officers()
        elif choice == '4':
            view_all_secret_points()
        elif choice == '5':
            break
        else:
            print("输入错误，请重新选择")
            time.sleep(1)


# ==================== 文件管理功能 ====================

def check_expiry():
    print("正在进行过期检查...")
    current_date = get_current_date()
    
    for i in list(document.keys()):
        doc = document[i]
        if doc.clearanceLevel >= 1:
            expiry = doc.expirationDate + doc.expirationYear * 10000
            if expiry <= current_date:
                current_path = get_clearance_path(doc.clearanceLevel)
                to_path = DIRS['unclassified']
                from_file = current_path + doc.name + ".txt"
                to_file = to_path + doc.name + ".txt"
                
                if os.path.exists(from_file):
                    shutil.copy2(from_file, to_file)
                    print(f"✓ {doc.name}已过保密期，自动解密中……")
                    add_audit_log("系统", "自动解密", doc.name, "成功", "保密期已过")
    
    print("检查完成！")
    time.sleep(1)
    os.system('cls' if os.name == 'nt' else 'clear')

def load_data():
    global staffCount, documentCount, staff, document
    
    create_directories()
    
    init_classification_basis()
    load_classification_officers()
    load_audit_logs()
    load_secret_points()
    
    if os.path.exists("Person.txt"):
        with open("Person.txt", "r", encoding='utf-8') as f:
            lines = f.readlines()
            if lines:
                staffCount = int(lines[0].strip())
                for i in range(1, staffCount + 1):
                    if i < len(lines):
                        parts = lines[i].strip().split()
                        if len(parts) >= 6:
                            staff[i] = Staff(
                                int(parts[0]), parts[1], parts[2],
                                int(parts[3]), int(parts[4]), int(parts[5])
                            )
    else:
        staffCount = 1
        staff[1] = Staff(1, "admin", "admin", 3, 3, 0)
        quick_save_person()  # 立即保存默认管理员
    
    if os.path.exists("File.txt"):
        with open("File.txt", "r", encoding='utf-8') as f:
            lines = f.readlines()
            if lines:
                documentCount = int(lines[0].strip())
                for i in range(1, documentCount + 1):
                    if i < len(lines):
                        parts = lines[i].strip().split()
                        if len(parts) >= 5:
                            document[i] = Document(
                                parts[0], int(parts[1]), int(parts[2]),
                                int(parts[3]), parts[4]
                            )
                            if len(parts) >= 6:
                                document[i].expirationYear = int(parts[5])
    
    check_expiry()

def save_data():
    print("工作辛苦了，数据正在备份……")
    quick_save_person()
    quick_save_file()
    save_classification_officers()
    save_audit_logs()
    save_secret_points()
    print("数据备份成功，再见！")


# ==================== 管理员界面 ====================

def admin_interface():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 50)
        print("        管理员界面")
        print("=" * 50)
        print("1. 增加涉密人员")
        print("2. 增加待定密文件")
        print("3. 添加定密责任人")
        print("4. 查看定密责任人")
        print("5. 查看审计日志")
        print("6. 🤖 批量AI文件分析")
        print("7. 退出系统")
        print("-" * 50)
        
        option = input("请输入您的操作：").strip()
        while option not in ['1', '2', '3', '4', '5', '6', '7']:
            option = input("输入格式错误，请重新输入操作：").strip()
        
        if option == '1':
            os.system('cls' if os.name == 'nt' else 'clear')
            global staffCount
            staffCount += 1
            print("=" * 40)
            print("          增加涉密人员")
            print("=" * 40)
            username = input("请输入涉密人员账号：")
            passcode = input("请输入涉密人员密码：")
            clearance = input("请输入涉密人员定密权限（0：非密，1：秘密，2：机密，3：绝密）：")
            while clearance not in ['0', '1', '2', '3']:
                clearance = input("输入格式错误，请重新输入定密权限：")
            
            staff[staffCount] = Staff(0, username, passcode, int(clearance), int(clearance), 0)
            
            # ✅ 立即保存人员数据到Person.txt
            quick_save_person()
            
            print(f"\n✓ 人员 {username} 添加成功！")
            add_audit_log("admin", "添加人员", username, "成功", f"密级:{clearance}")
            time.sleep(1)
        
        elif option == '2':
            os.system('cls' if os.name == 'nt' else 'clear')
            global documentCount
            documentCount += 1
            print("=" * 40)
            print("          增加待定密文件")
            print("=" * 40)
            filename = input("请输入文件名：")
            document[documentCount] = Document(filename, -1, 0, 0, "2333333333", 0)
            
            file_path = DIRS['unknown'] + filename + ".txt"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"这是一个待定密的文件：{filename}\n")
                f.write("请对此文件进行定密操作。\n")
            
            # ✅ 立即保存文件数据到File.txt
            quick_save_file()
            
            print(f"\n✓ 文件 {filename} 添加成功！")
            add_audit_log("admin", "添加文件", filename, "成功", "待定密")
            time.sleep(1)
        
        elif option == '3':
            add_classification_officer()
        
        elif option == '4':
            view_classification_officers()
        
        elif option == '5':
            view_audit_logs()
        
        elif option == '6':
            batch_ai_analysis()
        
        else:
            break


# ==================== 普通人员界面 ====================

def staff_interface(current_staff):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 50)
        print(f"    涉密人员：{staff[current_staff].username}")
        print(f"    当前密级：{get_level_name(staff[current_staff].clearance)}")
        print("=" * 50)
        print("1. 使用文件")
        print("2. 文件定密")
        print("3. 秘密变更")
        print("4. 定密授权")
        print("5. 密点标注")
        print("6. 定密监督")
        print("7. 🤖 AI辅助密点识别")
        print("8. 退出系统")
        print("-" * 50)
        
        option = input("请输入您的操作：").strip()
        while option not in ['1', '2', '3', '4', '5', '6', '7', '8']:
            option = input("输入格式错误，请重新输入操作：").strip()
        
        if option == '1':
            os.system('cls' if os.name == 'nt' else 'clear')
            filename = input("请输入你想要阅读的文件名：")
            
            file_found = None
            for i in range(1, documentCount + 1):
                if document[i].name == filename:
                    file_found = i
                    break
            
            if file_found is None:
                print("✗ 文件不存在，即将返回主界面！")
            elif document[file_found].clearanceLevel == -1:
                print("✗ 文件尚未定密，即将返回主界面！")
            elif document[file_found].clearanceLevel > staff[current_staff].clearance:
                print("✗ 密级不够，访问受限！")
            else:
                print(f"文件密级：{get_level_name(document[file_found].clearanceLevel)}")
                print("请输入访问口令：")
                access_granted = False
                for attempt in range(3):
                    pwd = input()
                    if pwd == document[file_found].accessKey:
                        access_granted = True
                        break
                    print(f"口令错误，还有{2-attempt}次机会：")
                
                if not access_granted:
                    print("✗ 访问口令错误，自动返回主界面！")
                    add_audit_log(staff[current_staff].username, "访问文件", filename, "失败", "口令错误")
                else:
                    print("✓ 权限访问正确，文件即将复制到你的文件夹！")
                    from_path = get_clearance_path(document[file_found].clearanceLevel) + filename + ".txt"
                    to_path = DIRS['use'] + filename + ".txt"
                    if os.path.exists(from_path):
                        shutil.copy2(from_path, to_path)
                        print(f"✓ 文件已复制到 {to_path}")
                        add_audit_log(staff[current_staff].username, "访问文件", filename, "成功", "阅读")
                        view_secret_points(filename)
                    else:
                        print("✗ 文件不存在于密级目录中！")
            
            time.sleep(2)
        
        elif option == '2':
            os.system('cls' if os.name == 'nt' else 'clear')
            filename = input("请输入你想要定密的文件名：")
            
            file_found = None
            for i in range(1, documentCount + 1):
                if document[i].name == filename:
                    file_found = i
                    break
            
            if file_found is None:
                print("✗ 不存在这个文件，即将返回主界面！")
            elif document[file_found].clearanceLevel != -1:
                print("✗ 这个文件已经定过密，请勿重复操作！")
            else:
                level = input("请输入你想定的密级（1：秘密，2：机密，3：绝密）：")
                while level not in ['1', '2', '3']:
                    level = input("输入格式错误，请重新输入定密级别：")
                
                if staff[current_staff].clearance >= int(level):
                    selected_basis = select_classification_basis()
                    
                    years = input("请输入保密年限：")
                    while not years.isdigit():
                        years = input("输入格式错误，请重新输入年限：")
                    
                    document[file_found].clearanceLevel = int(level)
                    document[file_found].expirationYear = int(years)
                    document[file_found].expirationDate = get_current_date()
                    document[file_found].handledBy = current_staff
                    
                    from_path = DIRS['unknown'] + filename + ".txt"
                    to_path = get_clearance_path(int(level)) + filename + ".txt"
                    if os.path.exists(from_path):
                        shutil.copy2(from_path, to_path)
                        os.remove(from_path)
                    
                    record = ClassificationRecord(
                        filename, staff[current_staff].username,
                        selected_basis.basis_id if selected_basis else "UNKNOWN",
                        -1, int(level), f"依据：{selected_basis.basis_name if selected_basis else '未知'}"
                    )
                    classification_records.append(record)
                    
                    # ✅ 定密后立即保存文件数据
                    quick_save_file()
                    
                    print(f"\n✓ 定密成功！文件已被定为{get_level_name(int(level))}")
                    add_audit_log(staff[current_staff].username, "文件定密", filename, "成功", 
                                 f"密级:{level}, 依据:{selected_basis.basis_name if selected_basis else '无'}")
                else:
                    print("✗ 你没有权限进行此操作！")
            
            time.sleep(2)
        
        elif option == '3':
            os.system('cls' if os.name == 'nt' else 'clear')
            filename = input("请输入你想变更秘密的文件名：")
            
            file_found = None
            for i in range(1, documentCount + 1):
                if document[i].name == filename:
                    file_found = i
                    break
            
            if file_found is None:
                print("✗ 不存在这个文件，即将返回主界面！")
            elif document[file_found].clearanceLevel > staff[current_staff].clearance:
                print("✗ 你没有权限进行此操作！")
            elif 1 <= document[file_found].clearanceLevel <= staff[current_staff].clearance:
                print(f"当前密级：{get_level_name(document[file_found].clearanceLevel)}")
                new_level = input("请输入你想变更的密级（0：非密，1：秘密，2：机密，3：绝密）：")
                while new_level not in ['0', '1', '2', '3']:
                    new_level = input("输入格式错误，请重新输入密级：")
                
                if int(new_level) <= staff[current_staff].clearance:
                    if int(new_level) == document[file_found].clearanceLevel:
                        print("✗ 变更失败，不可以变更为原来的密级！")
                    else:
                        old_level = document[file_found].clearanceLevel
                        new_level_int = int(new_level)
                        document[file_found].clearanceLevel = new_level_int
                        document[file_found].expirationDate = get_current_date()
                        document[file_found].handledBy = current_staff

                        # ✅ 添加文件移动逻辑
                        from_path = get_clearance_path(old_level) + filename + ".txt"
                        to_path = get_clearance_path(new_level_int) + filename + ".txt"

                        # 如果原文件存在，移动到新目录
                        if os.path.exists(from_path):
                            shutil.copy2(from_path, to_path)
                            os.remove(from_path)
                            print(f"✓ 文件已从 {get_level_name(old_level)} 目录移动到 {get_level_name(new_level_int)} 目录")
                        else:
                            print(f"⚠️ 警告：原文件不存在于 {from_path}")

                        selected_basis = select_classification_basis()

                        record = ClassificationRecord(
                            filename, staff[current_staff].username,
                            selected_basis.basis_id if selected_basis else "UNKNOWN",
                            old_level, new_level_int, f"密级变更"
                        )
                        classification_records.append(record)

                        quick_save_file()
                        
                        print(f"\n✓ 密级变更成功！新密级：{get_level_name(int(new_level))}")
                        add_audit_log(staff[current_staff].username, "密级变更", filename, "成功",
                                     f"{get_level_name(old_level)} -> {get_level_name(int(new_level))}")
                else:
                    print("✗ 密级变更失败，你没有权限进行此操作！")
            else:
                print("✗ 该文件尚未定密，请前往定密界面定密！")
            
            time.sleep(2)
        
        elif option == '4':
            os.system('cls' if os.name == 'nt' else 'clear')
            target_user = input("请输入你想要授权定密的涉密人员账号：")
            
            staff_found = None
            for i in range(1, staffCount + 1):
                if staff[i].username == target_user:
                    staff_found = i
                    break
            
            if staff_found is None:
                print("✗ 不存在这个账号，即将返回主界面！")
            elif staff[staff_found].originalClearance > staff[current_staff].clearance:
                print("✗ 你没有权限进行此操作！")
            else:
                print(f"目标用户当前权限：{get_level_name(staff[staff_found].clearance)}")
                auth_level = input("请输入授权密级（0：非密，1：秘密，2：机密，3：绝密）：")
                while auth_level not in ['0', '1', '2', '3']:
                    auth_level = input("输入格式错误，请重新输入授权密级：")
                
                if int(auth_level) <= staff[current_staff].clearance:
                    if staff[staff_found].originalClearance > int(auth_level):
                        print("✗ 定密授权失败，不可以低于原来定密权限！")
                    else:
                        old_level = staff[staff_found].clearance
                        staff[staff_found].clearance = int(auth_level)
                        staff[staff_found].authorizedBy = current_staff
                        
                        # ✅ 授权后立即保存人员数据
                        quick_save_person()
                        
                        print(f"\n✓ 定密授权成功！{target_user} 的新权限为{get_level_name(int(auth_level))}")
                        add_audit_log(staff[current_staff].username, "定密授权", target_user, "成功",
                                     f"{get_level_name(old_level)} -> {get_level_name(int(auth_level))}")
                else:
                    print("✗ 定密授权失败，你没有权限进行此操作！")
            
            time.sleep(2)
        
        elif option == '5':
            os.system('cls' if os.name == 'nt' else 'clear')
            filename = input("请输入要标注密点的文件名：")
            
            file_found = None
            for i in range(1, documentCount + 1):
                if document[i].name == filename:
                    file_found = i
                    break
            
            if file_found is None:
                print("✗ 文件不存在！")
                time.sleep(1)
            elif document[file_found].clearanceLevel == -1:
                print("✗ 文件尚未定密，请先定密！")
                time.sleep(1)
            elif document[file_found].clearanceLevel <= staff[current_staff].clearance:
                add_secret_point(filename, staff[current_staff].username)
            else:
                print("✗ 你没有权限操作该文件！")
                time.sleep(1)
        
        elif option == '6':
            supervision_interface()
        
        elif option == '7':
            filename = input("请输入要分析的文件名：")
            ai_assisted_secret_point(filename, staff[current_staff].username)
        
        else:
            break


# ==================== 主函数 ====================

def main():
    load_data()
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 50)
        print("    定密工作数字化管理系统")
        print("=" * 50)
        print("        欢迎使用本系统")
        print("=" * 50)
        print("\n请输入账号和密码：")
        
        username = input("账号：")
        password = input("密码：")
        
        staff_found = None
        for i in range(1, staffCount + 1):
            if staff[i].username == username and staff[i].passcode == password:
                staff_found = i
                break
        
        if staff_found is None:
            print("\n✗ 账号或密码错误，即将返回登录界面！")
            time.sleep(2)
        elif staff[staff_found].isAdmin == 1:
            admin_interface()
        else:
            staff_interface(staff_found)
    
    save_data()


if __name__ == "__main__":
    main()