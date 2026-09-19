#!/usr/bin/env python3
"""
纸笔外语学案 - 结构完整性检查器
Paper-and-Pencil Language Learning - Structure Integrity Checker
v2.0: 已移除自由写作功能，聚焦翻译与转换训练

检查项：
- 读写译任务比例是否均衡
- CEFR 等级一致性验证
- 语法脚手架充分性检查
- 翻译准确性标准评估
- 答案完整性验证
- 翻译难度梯度合理性
"""

import os
import sys
import re
import json
import yaml
import hashlib
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


class CheckStatus(Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    REVISE = "REVISE"


@dataclass
class CheckResult:
    status: CheckStatus
    check_type: str
    message: str
    details: Dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "check_type": self.check_type,
            "message": self.message,
            "details": self.details
        }


class PaperLanguageStructureChecker:
    """纸笔语言学案结构检查器"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.config = self._load_config()
        self.results: List[CheckResult] = []
        
    def _load_config(self) -> dict:
        """加载配置文件"""
        config_file = self.project_path / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {}
    
    def read_main_tex(self) -> str:
        """读取 main.tex 文件内容"""
        main_file = self.project_path / "main.tex"
        if main_file.exists():
            with open(main_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""
    
    def scan_all_sections(self) -> List[Tuple[str, str]]:
        """扫描所有章节文件"""
        sections = []
        for sec_file in sorted(self.project_path.glob("sec*.tex")):
            content = sec_file.read_text(encoding='utf-8')
            sections.append((sec_file.name, content))
        if not sections:
            main_file = self.project_path / "main.tex"
            if main_file.exists():
                sections.append((main_file.name, main_file.read_text(encoding='utf-8')))
        return sections
    
    def check_skill_balance(self) -> CheckResult:
        """检查读写任务比例"""
        tasks = {'reading': 0, 'writing': 0, 'grammar': 0, 'translation': 0}
        
        all_content = "\n".join([content for _, content in self.scan_all_sections()])
        
        # 统计各类任务数量（v2.0: 增加 translationtask 支持）
        tasks['reading'] = all_content.count(r'\begin{readingtask}')
        tasks['writing'] = all_content.count(r'\begin{writingscaffold}')  # v2.0 DEPRECATED
        tasks['grammar'] = all_content.count(r'\begin{grammardrill}')
        tasks['translation'] = all_content.count(r'\begin{translationbridge}') + \
                               all_content.count(r'\begin{translationtask}')
        
        total = sum(tasks.values())
        if total == 0:
            return CheckResult(
                status=CheckStatus.FAIL,
                check_type="skill_balance",
                message="未找到任何语言学习任务",
                details=tasks
            )
        
        # 计算百分比
        balance_ratio = {k: round(v/total*100, 1) for k, v in tasks.items()}
        
        # 理想比例（v2.0: 调整为目标分布）
        expected_reading = 30
        expected_writing = 10  # v2.0: 减少deprecated写作任务权重
        expected_grammar = 30
        expected_translation = 30  # v2.0: 提升翻译训练比重
        
        deviations = {
            'reading': abs(balance_ratio.get('reading', 0) - expected_reading),
            'writing': abs(balance_ratio.get('writing', 0) - expected_writing),
            'grammar': abs(balance_ratio.get('grammar', 0) - expected_grammar),
            'translation': abs(balance_ratio.get('translation', 0) - expected_translation)
        }
        
        max_deviation = max(deviations.values())
        
        if max_deviation > 15:
            return CheckResult(
                status=CheckStatus.WARNING,
                check_type="skill_balance",
                message=f"技能分布偏差较大，最大偏差 {max_deviation:.1f}%",
                details={"distribution": balance_ratio, "deviations": deviations}
            )
        else:
            return CheckResult(
                status=CheckStatus.PASS,
                check_type="skill_balance",
                message="技能分布合理",
                details={"distribution": balance_ratio}
            )
    
    def verify_cefr_consistency(self) -> CheckResult:
        """验证 CEFR 等级一致性"""
        cefr_markers = {}
        
        # 扫描所有 section 文件提取 CEFR 标记
        for sec_name, content in self.scan_all_sections():
            cefr_level = None
            
            # 查找 CEFR 等级标记
            for level in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
                if '\\cefr{' + level + '}' in content or '\\section*{.*' + level + '}' in content:
                    cefr_level = level
                    break
            
            if cefr_level:
                cefr_markers[sec_name] = cefr_level
        
        if not cefr_markers:
            return CheckResult(
                status=CheckStatus.WARNING,
                check_type="cefr_alignment",
                message="未检测到 CEFR 等级标记",
                details={}
            )
        
        # 检查难度递进是否合理
        levels_order = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        
        prev_level_idx = -1
        inconsistencies = []
        
        for sec_name, level in cefr_markers.items():
            curr_idx = levels_order.index(level)
            
            if curr_idx < prev_level_idx:
                inconsistencies.append({
                    "section": sec_name,
                    "current_level": level,
                    "previous_level": levels_order[prev_level_idx],
                    "issue": "CEFR 等级回退"
                })
            
            prev_level_idx = curr_idx
        
        if inconsistencies:
            return CheckResult(
                status=CheckStatus.WARNING,
                check_type="cefr_alignment",
                message=f"发现 {len(inconsistencies)} 处 CEFR 等级异常",
                details={"inconsistencies": inconsistencies}
            )
        else:
            return CheckResult(
                status=CheckStatus.PASS,
                check_type="cefr_alignment",
                message="CEFR 等级递进合理",
                details={"levels_by_section": cefr_markers}
            )
    
    def check_scaffolding_adequacy(self) -> CheckResult:
        """检查脚手架充分性（v2.0: 调整用于翻译任务）"""
        issues = []
        
        all_content = "\n".join([content for _, content in self.scan_all_sections()])
        
        # v2.0: 检查翻译任务的脚手架
        translation_tasks = all_content.count(r'\begin{translationtask}')
        old_trans = all_content.count(r'\begin{translationbridge}')
        total_trans = translation_tasks + old_trans
        
        # 应有关键词汇对照
        keywords_count = all_content.count(r'\keywordsstart')
        if translation_tasks > 0 and keywords_count < translation_tasks * 0.7:
            issues.append({
                "type": "insufficient_keywords",
                "description": f"翻译任务 {translation_tasks}个，但关键词汇对照不足 (仅{keywords_count}组)"
            })
        
        # 应有语法焦点提示
        syntax_focus = all_content.count(r'\syntaxfocus')
        if translation_tasks > 0 and syntax_focus < translation_tasks * 0.5:
            issues.append({
                "type": "missing_syntax_focus", 
                "description": f"缺少语法焦点提示"
            })
        
        # 旧版写作脚手架（deprecated）
        writing_tasks = all_content.count(r'\begin{writingscaffold}')
        if writing_tasks > 0:
            model_count = all_content.count(r'\modelparagraph')
            if model_count < writing_tasks * 0.5:
                issues.append({
                    "type": "deprecated_writing_task",
                    "description": f"写作任务已废弃，建议改用 translationtask",
                    "warning": True
                })
        
        if issues:
            return CheckResult(
                status=CheckStatus.WARNING,
                check_type="scaffolding",
                message=f"发现 {len(issues)} 处脚手架问题",
                details={"issues": issues}
            )
        else:
            return CheckResult(
                status=CheckStatus.PASS,
                check_type="scaffolding",
                message="翻译脚手架充足",
                details={"total_translation_tasks": total_trans}
            )
    
    def validate_rubrics(self) -> CheckResult:
        """验证评分标准清晰度（v2.0 翻译标准）"""
        all_content = "\n".join([content for _, content in self.scan_all_sections()])
        
        # 检查翻译任务是否有相应评估标准
        translation_tasks = all_content.count(r'\begin{translationtask}')
        old_trans = all_content.count(r'\begin{translationbridge}')
        total_trans = translation_tasks + old_trans
        
        # 翻译任务应有 solution
        solutions = all_content.count(r'\begin{solution}')
        teacher_notes = all_content.count(r'\begin{teacherNote}')
        
        if total_trans > 0 and solutions < total_trans:
            return CheckResult(
                status=CheckStatus.FAIL,
                check_type="rubric",
                message="翻译任务缺乏参考答案",
                details={"translation_tasks": total_trans, "solutions": solutions}
            )
        
        if total_trans > 0 and teacher_notes < total_trans * 0.5:
            return CheckResult(
                status=CheckStatus.WARNING,
                check_type="rubric",
                message="翻译任务缺少教学备注",
                details={"translation_tasks": total_trans, "notes": teacher_notes}
            )
        
        return CheckResult(
            status=CheckStatus.PASS,
            check_type="rubric",
            message="评分标准清晰",
            details={"tasks": total_trans}
        )
    
    def check_translation_fidelity(self) -> CheckResult:
        """检查翻译任务的翻译质量（v2.0 新增）"""
        all_content = "\n".join([content for _, content in self.scan_all_sections()])
        
        # 统计翻译任务数量
        translation_tasks = all_content.count(r'\begin{translationtask}')
        old_trans = all_content.count(r'\begin{translationbridge}')
        total_trans = translation_tasks + old_trans
        
        if total_trans == 0:
            return CheckResult(
                status=CheckStatus.WARNING,
                check_type="translation_fidelity",
                message="未检测到翻译任务，建议每单元至少包含 2 个翻译练习",
                details={}
            )
        
        # 检查关键词汇对照和语法焦点已在 scaffolding_adequacy 中检查
        # 此处增加对中文原文质量的简单检查
        chinese_count = all_content.count(r'\chinesetext') + all_content.count(r'\begin{chinesetext}')
        if translation_tasks > 0 and chinese_count < translation_tasks:
            return CheckResult(
                status=CheckStatus.FAIL,
                check_type="translation_fidelity",
                message="翻译任务缺少中文原文框",
                details={"tasks": translation_tasks, "chinese_boxes": chinese_count}
            )
        
        return CheckResult(
            status=CheckStatus.PASS,
            check_type="translation_fidelity",
            message="翻译任务设计合理",
            details={"total_tasks": total_trans}
        )
    
    def check_lexical_equivalence(self) -> CheckResult:
        """检查关键短语对照充分性（v2.0 新增）"""
        all_content = "\n".join([content for _, content in self.scan_all_sections()])
        
        # 统计译文条目
        trans_keywords = len(re.findall(r'\\item\s+[^:\n]+:\s+.*', all_content))  # Key: Value 格式
        if trans_keywords < 10:
            return CheckResult(
                status=CheckStatus.WARNING,
                check_type="lexical_equivalence",
                message="关键词汇对照较少，建议每单元至少 10 组",
                details={"pairs_found": trans_keywords}
            )
        
        return CheckResult(
            status=CheckStatus.PASS,
            check_type="lexical_equivalence",
            message=f"词汇对照充分 ({trans_keywords}组)",
            details={"pairs_found": trans_keywords}
        )
    
    def check_self_assessment_feasibility(self) -> CheckResult:
        """验证翻译答案的可自评性（v2.0 新增）"""
        all_content = "\n".join([content for _, content in self.scan_all_sections()])
        
        # 翻译任务应有明确的 solution 环境
        solutions = all_content.count(r'\begin{solution}')
        teacher_notes = all_content.count(r'\begin{teacherNote}')
        
        translation_tasks = all_content.count(r'\begin{translationtask}')
        old_trans = all_content.count(r'\begin{translationbridge}')
        total_trans = translation_tasks + old_trans
        
        if total_trans > 0:
            if solutions < total_trans:
                return CheckResult(
                    status=CheckStatus.FAIL,
                    check_type="self_assessment",
                    message="翻译任务缺少参考答案",
                    details={"tasks": total_trans, "solutions": solutions}
                )
            
            if teacher_notes < total_trans * 0.5:
                return CheckResult(
                    status=CheckStatus.WARNING,
                    check_type="self_assessment",
                    message="缺少教师备注，不利于学生自学时获得指导",
                    details={"tasks": total_trans, "notes": teacher_notes}
                )
        
        return CheckResult(
            status=CheckStatus.PASS,
            check_type="self_assessment",
            message="翻译答案可自评性强",
            details={"tasks": total_trans, "solutions": solutions, "notes": teacher_notes}
        )
    
    def check_answer_completeness(self) -> CheckResult:
        """检查答案完整性"""
        missing_solutions = []
        
        for sec_name, content in self.scan_all_sections():
            question_count = content.count(r'\question')
            solution_count = content.count(r'\begin{solution}')
            
            if question_count > solution_count:
                missing_solutions.append({
                    "section": sec_name,
                    "questions": question_count,
                    "solutions": solution_count,
                    "missing": question_count - solution_count
                })
        
        if missing_solutions:
            return CheckResult(
                status=CheckStatus.FAIL,
                check_type="answers",
                message=f"发现 {len(missing_solutions)} 节缺少完整答案",
                details={"sections": missing_solutions}
            )
        
        return CheckResult(
            status=CheckStatus.PASS,
            check_type="answers",
            message="答案完整"
        )
    
    def check_genre_diversity(self) -> CheckResult:
        """检查体裁多样性"""
        genres_found = set()
        
        for sec_name, content in self.scan_all_sections():
            if r'\genre{narrative}' in content:
                genres_found.add('narrative')
            if r'\genre{exposition}' in content:
                genres_found.add('exposition')
            if r'\genre{argumentation}' in content:
                genres_found.add('argumentation')
            if r'\genre{correspondence}' in content:
                genres_found.add('correspondence')
        
        if len(genres_found) < 2:
            return CheckResult(
                status=CheckStatus.WARNING,
                check_type="genre_diversity",
                message=f"体裁单一，仅发现 {len(genres_found)} 种",
                details={"genres": list(genres_found)}
            )
        
        return CheckResult(
            status=CheckStatus.PASS,
            check_type="genre_diversity",
            message=f"体裁多样 ({len(genres_found)} 种)",
            details={"genres": list(genres_found)}
        )
    
    def run_all_checks(self) -> dict:
        """运行所有检查"""
        checks = [
            self.check_skill_balance,
            self.verify_cefr_consistency,
            self.check_scaffolding_adequacy,  # 仍用于检查翻译脚手架
            self.validate_rubrics,
            self.check_answer_completeness,
            self.check_genre_diversity,
            # v2.0 新增检查项
            self.check_translation_fidelity,
            self.check_lexical_equivalence,
            self.check_self_assessment_feasibility
        ]
        
        results = []
        all_pass = True
        
        for check in checks:
            result = check()
            results.append(result.to_dict())
            if result.status != CheckStatus.PASS:
                all_pass = False
        
        return {
            "schema_version": 2,
            "status": "PASS" if all_pass else "REVIEW",
            "input_digest": self._calculate_input_digest(),
            "pdf_sha256": "",  # TODO: 实际 PDF 生成后填充
            "checks": results,
            "tool_version": "1.0"
        }
    
    def _calculate_input_digest(self) -> str:
        """计算输入摘要"""
        hasher = hashlib.sha256()
        
        # 读取 main.tex
        main_content = self.read_main_tex()
        hasher.update(main_content.encode('utf-8'))
        
        # 读取所有章节
        for _, content in self.scan_all_sections():
            hasher.update(content.encode('utf-8'))
        
        return hasher.hexdigest()[:32]
    
    def run_json_output(self):
        """以 JSON 格式输出结果"""
        result = self.run_all_checks()
        print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description='纸笔语言学案结构检查器')
    parser.add_argument('project', help='项目路径')
    parser.add_argument('--json', action='store_true', help='JSON 格式输出')
    
    args = parser.parse_args()
    
    checker = PaperLanguageStructureChecker(args.project)
    
    if args.json:
        checker.run_json_output()
    else:
        result = checker.run_all_checks()
        print(f"总体状态：{result['status']}")
        print(f"\n详细检查结果:")
        for check in result['checks']:
            status_icon = {"PASS": "✓", "WARNING": "⚠", "FAIL": "✗"}[check['status']]
            print(f"\n{status_icon} {check['check_type']}: {check['message']}")
            if check.get('details'):
                for key, value in check['details'].items():
                    print(f"  - {key}: {value}")


if __name__ == "__main__":
    main()
