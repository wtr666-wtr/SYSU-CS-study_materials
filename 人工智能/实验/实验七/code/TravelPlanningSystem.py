"""
智能旅行规划系统 (Travel Planning Multi-Agent System)
基于 LangGraph + LangChain
"""
import os
os.environ["OPENAI_API_KEY"] = "sk-422a30c66061427cbc47d89a5712540d"
os.environ["OPENAI_BASE_URL"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"
import os
import json
import operator
from datetime import datetime
from typing import List, Dict, Any, TypedDict, Annotated, Optional
from pathlib import Path

# ============ 1. 导入依赖 (开源框架) ============
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langchain_core.tools import tool

# 修复：使用 langchain_community 的路径
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.docstore.document import Document

print("✅ 所有依赖导入成功")

# ============ 2. 配置模型 ============
API_KEY = "sk-ws-H.EDMIYLI.stbZ.MEQCIEeuQdKw68rZoVJJSfCMbHqx6vAQ3xEjkog-O82gGm8GAiBtcSesTaLKkSAggr-hMSuricfu7sfrN-DBTHTcOPxogA"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

model = ChatOpenAI(
    model="qwen-turbo",
    base_url=BASE_URL,
    api_key=API_KEY,
    temperature=0.7
)

print("✅ 模型配置完成")

# ============ 3. 工具定义 (2种以上) ============

@tool
def search_attractions(query: str) -> str:
    """搜索旅游景点和活动信息"""
    results = {
        "beach": "🏖️ 沙滩度假推荐: 普吉岛、巴厘岛、马尔代夫。最佳季节: 11月-次年4月。人均预算: 5000-15000元。",
        "mountain": "🏔️ 山地旅行推荐: 黄山、张家界、峨眉山。最佳季节: 春秋两季。人均预算: 3000-8000元。",
        "city": "🏙️ 城市旅行推荐: 北京、上海、成都、西安。适合全年旅行。人均预算: 2000-10000元。",
        "culture": "🏛️ 文化体验推荐: 故宫、长城、莫高窟、丽江古城。适合深度文化游。"
    }
    for key, value in results.items():
        if key in query.lower():
            return value
    return "🔍 热门旅游目的地: 三亚、厦门、杭州、桂林、九寨沟"

@tool
def calculate_budget(params: str) -> str:
    """计算旅行预算"""
    budgets = {
        "economy": "💰 经济型预算: 交通(30%) + 住宿(25%) + 餐饮(20%) + 景点(15%) + 其他(10%) = 3000-5000元/人",
        "standard": "💰 标准型预算: 交通(25%) + 住宿(30%) + 餐饮(20%) + 景点(15%) + 购物(10%) = 5000-10000元/人",
        "luxury": "💰 豪华型预算: 交通(20%) + 住宿(35%) + 餐饮(25%) + 景点(10%) + 购物(10%) = 10000-30000元/人",
        "family": "👨‍👩‍👧‍👦 家庭旅行预算: 人均x3，建议增加亲子活动预算15%"
    }
    for key, value in budgets.items():
        if key in params.lower():
            return value
    return "💡 建议预算: 5000-8000元/人，根据旅行天数和目的地调整"

@tool
def rag_travel_knowledge(query: str) -> str:
    """RAG检索旅行相关知识"""
    knowledge_base = {
        "planning": """📚 旅行规划建议:
        1. 提前1-3个月规划行程
        2. 预订机票酒店可节省20-30%
        3. 制定详细日程，预留弹性时间
        4. 购买旅行保险
        5. 了解目的地文化习俗""",
        
        "packing": """🧳 行李打包清单:
        1. 证件: 身份证、护照、签证
        2. 衣物: 根据季节和天数准备
        3. 药品: 常用药、晕车药、创可贴
        4. 电子设备: 充电宝、转换插头
        5. 其他: 雨伞、防晒霜、水杯""",
        
        "safety": """🛡️ 旅行安全建议:
        1. 保管好贵重物品
        2. 选择正规交通工具
        3. 注意饮食卫生
        4. 遵守当地法律法规
        5. 保持联系，告知行程"""
    }
    for key, value in knowledge_base.items():
        if key in query.lower():
            return value
    return "📖 建议: 出行前做好充分准备，享受旅程"

# 工具列表
TOOLS = [search_attractions, calculate_budget, rag_travel_knowledge]

# ============ 4. 长期记忆系统 ============

class LongTermMemory:
    """基于FAISS向量数据库的长期记忆 - 使用DashScope嵌入"""
    
    def __init__(self, storage_path: str = "./travel_memory"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        # 使用 DashScope 的嵌入模型（通义千问官方支持）
        self.embeddings = DashScopeEmbeddings(
            model="text-embedding-v1",  # 通义千问的嵌入模型
            dashscope_api_key=API_KEY   # 使用您已有的API Key
        )
        print("✅ 使用 DashScope 嵌入模型 (text-embedding-v1)")
        
        self.vector_store = None
        self._load_or_create()
    
    def _load_or_create(self):
        index_path = self.storage_path / "index.faiss"
        if index_path.exists():
            try:
                self.vector_store = FAISS.load_local(
                    str(self.storage_path), 
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                print("✅ 长期记忆加载成功")
            except Exception as e:
                print(f"⚠️ 加载失败: {e}")
                self._create_new_store()
        else:
            self._create_new_store()
    
    def _create_new_store(self):
        initial_docs = [
            Document(page_content=text, metadata={"type": "initial"})
            for text in [
                "旅行规划要综合考虑预算、时间和兴趣",
                "好的旅行体验来自精心的准备和开放的心态",
                "安全永远是旅行的第一要务",
                "文化体验是旅行的核心价值",
                "灵活调整计划可以带来意外惊喜"
            ]
        ]
        self.vector_store = FAISS.from_documents(initial_docs, self.embeddings)
        self.save()
        print("✅ 长期记忆创建成功")
    
    def save(self):
        if self.vector_store:
            self.vector_store.save_local(str(self.storage_path))
    
    def add_memory(self, content: str, metadata: Dict = None):
        if metadata is None:
            metadata = {}
        metadata["timestamp"] = datetime.now().isoformat()
        doc = Document(page_content=content, metadata=metadata)
        self.vector_store.add_documents([doc])
        self.save()
    
    def retrieve_memories(self, query: str, k: int = 3) -> List[str]:
        if self.vector_store is None:
            return []
        docs = self.vector_store.similarity_search(query, k=k)
        return [doc.page_content for doc in docs]

# ============ 5. 状态定义 ============

class AgentState(TypedDict):
    messages: Annotated[List[Dict[str, str]], operator.add]
    current_speaker: str
    planning_phase: int
    max_phases: int
    terminated: bool
    destination: str
    travel_days: int
    budget_type: str
    analysis_results: Dict[str, Any]
    final_plan: Optional[str]

# ============ 6. 智能体类 (含短期+长期记忆) ============

class TravelAgent:
    """旅行规划智能体 - 包含短期和长期记忆"""
    
    def __init__(self, name: str, role: str, system_prompt: str):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        
        # 短期记忆 (对话缓冲区)
        self.short_term_memory: List[Dict] = []
        self.memory_window = 10
        
        # 长期记忆 (向量数据库)
        self.long_term_memory = LongTermMemory()
    
    def update_short_term_memory(self, message: Dict):
        """更新短期记忆"""
        self.short_term_memory.append(message)
        if len(self.short_term_memory) > self.memory_window:
            self.short_term_memory.pop(0)
    
    def update_long_term_memory(self, content: str, metadata: Dict = None):
        """更新长期记忆"""
        self.long_term_memory.add_memory(content, metadata)
    
    def get_short_term_context(self) -> str:
        """获取短期记忆上下文"""
        if not self.short_term_memory:
            return "暂无近期对话"
        return "\n".join([
            f"{m['speaker']}: {m['content'][:200]}"
            for m in self.short_term_memory[-5:]
        ])
    
    def get_long_term_context(self, query: str) -> str:
        """获取长期记忆上下文"""
        memories = self.long_term_memory.retrieve_memories(query, k=2)
        if not memories:
            return "暂无历史经验"
        return "\n".join([f"[历史经验] {m[:200]}" for m in memories])
    
    def get_context(self, topic: str = None, extra: str = "") -> str:
        """获取完整上下文 (短期+长期)"""
        short_term = self.get_short_term_context()
        long_term = self.get_long_term_context(topic or "旅行规划")
        
        return f"""
{self.system_prompt}

【短期记忆 - 最近对话】
{short_term}

【长期记忆 - 历史经验】
{long_term}

{extra}

请根据以上信息，结合你的角色定位进行发言。
"""

# ============ 7. 推理方法 ============

class ReasoningMethods:
    """推理方法集合"""
    
    @staticmethod
    def tree_of_thought(destination: str) -> str:
        """思维树推理 (ToT)"""
        return f"""
请使用"思维树(ToT)"方法为 {destination} 规划行程：

🌳 路径1: 文化体验深度游
- 历史遗迹、博物馆、民俗体验
- 适合喜欢历史文化的旅行者
- 建议停留3-5天

🌳 路径2: 自然风光休闲游
- 山水风光、海滩度假、户外活动
- 适合放松身心的旅行者
- 建议停留4-7天

🌳 路径3: 美食购物城市游
- 特色美食、购物商圈、城市地标
- 适合喜欢都市生活的旅行者
- 建议停留2-4天

请对每条路径深入分析，选择最适合的行程方案。
"""
    
    @staticmethod
    def react_with_tools(tools_results: Dict) -> str:
        """ReAct推理"""
        return f"""
请使用"ReAct"方法设计旅行体验：

🧠 思考(Think):
旅行者的核心需求是什么？
如何创造难忘的旅行体验？

🔍 推理(Reason):
结合工具信息进行分析：
- 景点信息: {tools_results.get('attractions', '无')}
- 预算参考: {tools_results.get('budget', '无')}
- 旅行知识: {tools_results.get('knowledge', '无')}

⚡ 行动(Act):
基于推理，设计具体的行程安排和体验活动。
"""
    
    @staticmethod
    def reflection(role: str) -> str:
        """反思推理 (Reflection)"""
        return f"""
请使用"反思(Reflection)"方法优化规划：

🔍 回顾(Review):
你之前的规划方案是什么？依据是什么？

🤔 批判(Critique):
规划可能存在哪些不足？
有无遗漏重要因素？

💡 改进(Improve):
如何改进方案使其更完善？
有无更好的替代方案？

📈 升华(Elevate):
如何让旅行体验更有价值？
对旅行者有什么建议？
"""

# ============ 8. 创建6个智能体 ============

print("🤖 创建旅行规划团队...\n")

# 智能体1: 旅行协调员 (使用Reflection)
coordinator = TravelAgent(
    "TravelCoordinator",
    "旅行协调员",
    """👔 你是旅行协调员，负责统筹整个旅行规划过程。

【职责】
1. 协调团队工作
2. 综合各方建议
3. 使用Reflection方法反思规划
4. 确保规划完整可行

【推理方法】Reflection(反思)"""
)

# 智能体2: 预算分析师
budget_expert = TravelAgent(
    "BudgetExpert",
    "预算分析师",
    """💰 你是预算分析师，负责旅行预算规划。

【职责】
1. 分析各项费用
2. 制定合理预算
3. 优化费用分配
4. 提供省钱建议

【推理方法】标准推理"""
)

# 智能体3: 旅行研究员 (使用ToT)
research_specialist = TravelAgent(
    "ResearchSpecialist",
    "旅行研究员",
    """🔍 你是旅行研究员，负责深度研究目的地。

【职责】
1. 研究目的地特色
2. 挖掘独特体验
3. 提供专业建议

【推理方法】ToT(思维树)"""
)

# 智能体4: 体验设计师 (使用ReAct)
experience_designer = TravelAgent(
    "ExperienceDesigner",
    "体验设计师",
    """🎨 你是体验设计师，负责设计旅行体验。

【职责】
1. 设计每日行程
2. 安排特色活动
3. 创造难忘体验

【推理方法】ReAct(推理+行动)
【工具】search_attractions, calculate_budget, rag_travel_knowledge"""
)

# 智能体5: 风险顾问 (使用Reflection)
risk_advisor = TravelAgent(
    "RiskAdvisor",
    "风险顾问",
    """🛡️ 你是风险顾问，负责评估旅行风险。

【职责】
1. 识别潜在风险
2. 制定应对措施
3. 确保旅行安全

【推理方法】Reflection(反思)"""
)

# 智能体6: 旅行决策师
trip_decider = TravelAgent(
    "TripDecider",
    "旅行决策师",
    """✅ 你是旅行决策师，负责做出最终规划。

【职责】
1. 综合所有建议
2. 权衡各项因素
3. 制定最终方案"""
)

agents = [coordinator, budget_expert, research_specialist, 
          experience_designer, risk_advisor, trip_decider]
print(f"✅ 创建完成: {len(agents)} 个智能体")
for a in agents:
    print(f"   {a.name} - {a.role}")
print("")

# ============ 9. 节点函数 ============

def coordinator_node(state: AgentState) -> Dict:
    """旅行协调员节点"""
    destination = state.get("destination", "未知目的地")
    
    reflection = ReasoningMethods.reflection(coordinator.role)
    context = coordinator.get_context(destination, f"""
{reflection}

请作为旅行协调员开场，介绍规划流程，分配任务。
目的地：{destination}
旅行天数：{state.get('travel_days', 5)}天
预算类型：{state.get('budget_type', '标准')}
""")
    
    response = model.invoke([HumanMessage(content=context)])
    
    message = {"speaker": coordinator.name, "content": response.content}
    coordinator.update_short_term_memory(message)
    coordinator.update_long_term_memory(response.content)
    
    print(f"\n{'='*60}")
    print(f"👔 {coordinator.name} [{coordinator.role}] (Reflection)")
    print(f"{'='*60}")
    print(response.content)
    
    state["messages"].append(message)
    state["current_speaker"] = coordinator.name
    
    return {**state, "next": "budget_expert"}

def budget_expert_node(state: AgentState) -> Dict:
    """预算分析师节点"""
    context = budget_expert.get_context(
        state.get("destination", ""),
        f"请分析预算，旅行天数：{state.get('travel_days', 5)}天"
    )
    
    response = model.invoke([HumanMessage(content=context)])
    
    message = {"speaker": budget_expert.name, "content": response.content}
    budget_expert.update_short_term_memory(message)
    budget_expert.update_long_term_memory(response.content)
    
    print(f"\n{'='*60}")
    print(f"💰 {budget_expert.name} [{budget_expert.role}]")
    print(f"{'='*60}")
    print(response.content)
    
    state["messages"].append(message)
    state["current_speaker"] = budget_expert.name
    
    return {**state, "next": "research_specialist"}

def research_specialist_node(state: AgentState) -> Dict:
    """旅行研究员节点 (ToT)"""
    destination = state.get("destination", "")
    
    tot = ReasoningMethods.tree_of_thought(destination)
    context = research_specialist.get_context(destination, tot)
    
    response = model.invoke([HumanMessage(content=context)])
    
    message = {"speaker": research_specialist.name, "content": response.content}
    research_specialist.update_short_term_memory(message)
    research_specialist.update_long_term_memory(response.content)
    
    print(f"\n{'='*60}")
    print(f"🔍 {research_specialist.name} [{research_specialist.role}] (ToT)")
    print(f"{'='*60}")
    print(response.content)
    
    state["messages"].append(message)
    state["current_speaker"] = research_specialist.name
    
    return {**state, "next": "experience_designer"}

def experience_designer_node(state: AgentState) -> Dict:
    """体验设计师节点 (ReAct + 3工具)"""
    destination = state.get("destination", "")
    
    # 调用3种工具
    attractions = search_attractions.invoke(destination)
    budget = calculate_budget.invoke(state.get("budget_type", "standard"))
    knowledge = rag_travel_knowledge.invoke("planning safety")
    
    tools_results = {
        "attractions": attractions,
        "budget": budget,
        "knowledge": knowledge
    }
    
    react = ReasoningMethods.react_with_tools(tools_results)
    context = experience_designer.get_context(destination, react)
    
    response = model.invoke([HumanMessage(content=context)])
    
    message = {"speaker": experience_designer.name, "content": response.content}
    experience_designer.update_short_term_memory(message)
    experience_designer.update_long_term_memory(response.content)
    
    print(f"\n{'='*60}")
    print(f"🎨 {experience_designer.name} [{experience_designer.role}] (ReAct + 3工具)")
    print(f"{'='*60}")
    print(response.content)
    
    state["messages"].append(message)
    state["current_speaker"] = experience_designer.name
    
    return {**state, "next": "risk_advisor"}

def risk_advisor_node(state: AgentState) -> Dict:
    """风险顾问节点 (Reflection)"""
    destination = state.get("destination", "")
    
    reflection = ReasoningMethods.reflection(risk_advisor.role)
    context = risk_advisor.get_context(destination, f"""
{reflection}

请评估旅行风险，提供安全建议。
目的地：{destination}
""")
    
    response = model.invoke([HumanMessage(content=context)])
    
    message = {"speaker": risk_advisor.name, "content": response.content}
    risk_advisor.update_short_term_memory(message)
    risk_advisor.update_long_term_memory(response.content)
    
    print(f"\n{'='*60}")
    print(f"🛡️ {risk_advisor.name} [{risk_advisor.role}] (Reflection)")
    print(f"{'='*60}")
    print(response.content)
    
    state["messages"].append(message)
    state["current_speaker"] = risk_advisor.name
    state["planning_phase"] += 1
    
    if state["planning_phase"] < state["max_phases"]:
        return {**state, "next": "experience_designer"}
    else:
        return {**state, "next": "trip_decider"}

def trip_decider_node(state: AgentState) -> Dict:
    """旅行决策师节点"""
    print("\n" + "="*70)
    print("✅ 综合规划与最终决策")
    print("="*70)
    
    all_analyses = "\n".join([
        f"{m['speaker']}: {m['content'][:200]}..."
        for m in state["messages"][-6:]
    ])
    
    decision_prompt = f"""
基于所有专家的建议，制定最终旅行方案。

所有专家意见：
{all_analyses}

请按以下格式输出最终旅行方案：
【目的地】：
【旅行天数】：
【预算建议】：
【行程亮点】：
【风险提示】：
【最终建议】：
"""
    
    response = model.invoke([HumanMessage(content=decision_prompt)])
    state["final_plan"] = response.content
    
    print(f"\n{'='*60}")
    print(f"✅ {trip_decider.name} [{trip_decider.role}]")
    print(f"{'='*60}")
    print(response.content)
    print(f"{'='*60}\n")
    
    # 生成总结报告
    print("\n" + "="*70)
    print("📊 旅行规划总结报告")
    print("="*70)
    
    summary = f"""
【目的地】{state.get('destination', '未指定')}
【规划时间】{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
【参与智能体】{len(agents)}个

【专家贡献】
- 旅行协调员: 统筹规划
- 预算分析师: 费用分析
- 旅行研究员: 深度研究 (ToT)
- 体验设计师: 行程设计 (ReAct + 3工具)
- 风险顾问: 安全评估 (Reflection)

【最终方案】
{state["final_plan"]}
"""
    print(summary)
    
    state["terminated"] = True
    return {**state, "next": END}

# ============ 10. 构建图 ============

def build_travel_graph() -> StateGraph:
    """构建旅行规划流程图"""
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("budget_expert", budget_expert_node)
    workflow.add_node("research_specialist", research_specialist_node)
    workflow.add_node("experience_designer", experience_designer_node)
    workflow.add_node("risk_advisor", risk_advisor_node)
    workflow.add_node("trip_decider", trip_decider_node)
    
    # 设置流程
    workflow.add_edge("coordinator", "budget_expert")
    workflow.add_edge("budget_expert", "research_specialist")
    workflow.add_edge("research_specialist", "experience_designer")
    workflow.add_edge("experience_designer", "risk_advisor")
    workflow.add_edge("risk_advisor", "trip_decider")
    workflow.add_edge("trip_decider", END)
    
    workflow.set_entry_point("coordinator")
    
    return workflow.compile()

# ============ 11. 主函数 ============

def main():
    print("\n" + "="*70)
    print("✈️ 智能旅行规划系统")
    print("="*70)
    print("\n📋 系统配置清单:")
    print("  ✅ 智能体数量: 6个 (>=4)")
    print("  ✅ 推理方法: ToT + ReAct + Reflection")
    print("  ✅ 记忆机制: 短期记忆(10条) + 长期记忆(FAISS向量数据库)")
    print("  ✅ 工具: search_attractions + calculate_budget + rag_travel_knowledge")
    print("  ✅ 开源框架: LangGraph + LangChain")
    print("="*70)
    
    print("\n🤖 智能体列表:")
    print("  👔 TravelCoordinator   - 旅行协调员 (Reflection)")
    print("  💰 BudgetExpert        - 预算分析师 (标准推理)")
    print("  🔍 ResearchSpecialist  - 旅行研究员 (ToT)")
    print("  🎨 ExperienceDesigner  - 体验设计师 (ReAct + 3工具)")
    print("  🛡️ RiskAdvisor         - 风险顾问 (Reflection)")
    print("  ✅ TripDecider         - 旅行决策师 (综合决策)")
    print("="*70)
    
    print("\n⏳ 正在构建旅行规划图...")
    graph = build_travel_graph()
    print("✅ 图构建完成\n")
    
    # 初始状态
    initial_state = AgentState(
        messages=[],
        current_speaker="TravelCoordinator",
        planning_phase=0,
        max_phases=2,
        terminated=False,
        destination="云南大理",
        travel_days=5,
        budget_type="standard",
        analysis_results={},
        final_plan=None
    )
    
    print(f"🎯 开始规划: {initial_state['destination']}, {initial_state['travel_days']}天\n")
    
    try:
        for output in graph.stream(initial_state):
            pass
        print("\n✅ 旅行规划完成！")
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        print("提示：请检查网络连接和API密钥是否有效。")

if __name__ == "__main__":
    main()