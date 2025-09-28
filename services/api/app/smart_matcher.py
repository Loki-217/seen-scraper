# services/api/app/smart_matcher.py
from bs4 import BeautifulSoup
import difflib
from typing import List, Dict, Any

class SmartMatcher:
    """后端验证和优化选择器"""
    
    def validate_and_optimize(self, html: str, selector: str, sample_element: Dict) -> Dict:
        """验证前端生成的选择器，并优化"""
        soup = BeautifulSoup(html, 'lxml')
        
        # 测试选择器
        elements = soup.select(selector)
        
        if len(elements) < 2:
            # 选择器太严格，尝试放松
            optimized = self.relax_selector(selector, soup, sample_element)
            return optimized
        
        if len(elements) > 100:
            # 选择器太宽泛，尝试收紧
            optimized = self.tighten_selector(selector, soup, sample_element)
            return optimized
        
        # 验证内容一致性
        consistency = self.check_consistency(elements)
        
        return {
            'selector': selector,
            'count': len(elements),
            'consistency': consistency,
            'samples': self.extract_samples(elements[:5]),
            'optimized': False
        }
    
    def relax_selector(self, selector: str, soup: BeautifulSoup, sample: Dict) -> Dict:
        """放松选择器条件"""
        strategies = [
            # 移除:nth-child等
            lambda s: re.sub(r':nth-[^)]+\)', '', s),
            # 移除过于具体的class
            lambda s: s.split('.')[0] if '.' in s else s,
            # 使用更通用的父级
            lambda s: ' '.join(s.split(' ')[:-1]) if ' ' in s else s
        ]
        
        for strategy in strategies:
            new_selector = strategy(selector)
            if new_selector != selector:
                elements = soup.select(new_selector)
                if 2 <= len(elements) <= 100:
                    return {
                        'selector': new_selector,
                        'count': len(elements),
                        'optimized': True,
                        'optimization': 'relaxed'
                    }
        
        return {'selector': selector, 'optimized': False, 'error': 'Could not relax'}
    
    def check_consistency(self, elements: List) -> float:
        """检查元素的一致性"""
        if len(elements) < 2:
            return 1.0
        
        # 检查结构一致性
        structures = []
        for el in elements[:10]:  # 采样前10个
            structure = self._get_structure(el)
            structures.append(structure)
        
        # 计算相似度
        total_similarity = 0
        comparisons = 0
        
        for i in range(len(structures)):
            for j in range(i+1, len(structures)):
                similarity = difflib.SequenceMatcher(None, structures[i], structures[j]).ratio()
                total_similarity += similarity
                comparisons += 1
        
        return total_similarity / comparisons if comparisons > 0 else 0
    
    def _get_structure(self, element) -> str:
        """获取元素的结构特征"""
        features = []
        
        # 标签名
        features.append(element.name)
        
        # 子元素标签
        for child in element.children:
            if hasattr(child, 'name'):
                features.append(child.name)
        
        # 是否有特定内容
        text = element.get_text(strip=True)
        if '$' in text or '￥' in text:
            features.append('price')
        if element.find('img'):
            features.append('image')
        if element.find('a'):
            features.append('link')
            
        return '-'.join(features)