// services/web/js/smart-selector.js
class SmartSelector {
    /**
     * 用户点击示例后，智能识别所有相似元素
     */
    analyzeSimilarElements(clickedElement) {
        const strategies = [
            this.strategyBySameClass,      // 策略1: 相同class
            this.strategyByStructure,       // 策略2: 相同DOM结构
            this.strategyByVisualPattern,   // 策略3: 视觉模式
            this.strategyBySiblings,        // 策略4: 兄弟元素
            this.strategyBySemantics        // 策略5: 语义相似
        ];
        
        let bestMatch = null;
        let maxScore = 0;
        
        // 尝试每种策略，选择最佳匹配
        for (const strategy of strategies) {
            const result = strategy.call(this, clickedElement);
            if (result.score > maxScore) {
                maxScore = result.score;
                bestMatch = result;
            }
        }
        
        return this.visualizeSuggestion(bestMatch);
    }
    
    /**
     * 策略1: 通过相同的class查找
     */
    strategyBySameClass(element) {
        const classes = Array.from(element.classList)
            .filter(c => !c.includes('hover') && !c.includes('active'));
        
        if (classes.length === 0) {
            return { score: 0, elements: [] };
        }
        
        // 智能组合class
        const candidates = [];
        
        // 尝试单个class
        for (const cls of classes) {
            const elements = document.querySelectorAll(`.${cls}`);
            if (elements.length > 1 && elements.length < 100) {
                candidates.push({
                    selector: `.${cls}`,
                    elements: Array.from(elements),
                    score: this.calculateScore(element, elements)
                });
            }
        }
        
        // 尝试class组合
        if (classes.length > 1) {
            const selector = '.' + classes.join('.');
            const elements = document.querySelectorAll(selector);
            if (elements.length > 1) {
                candidates.push({
                    selector,
                    elements: Array.from(elements),
                    score: this.calculateScore(element, elements) + 0.1 // 组合加分
                });
            }
        }
        
        return candidates.sort((a, b) => b.score - a.score)[0] || { score: 0 };
    }
    
    /**
     * 策略2: 通过DOM结构查找
     */
    strategyByStructure(element) {
        // 获取元素的结构指纹
        const fingerprint = this.getStructureFingerprint(element);
        
        // 查找具有相似结构的容器
        const parent = this.findRepeatingContainer(element);
        if (!parent) return { score: 0 };
        
        // 在容器内查找相似结构
        const similar = [];
        const children = parent.children;
        
        for (const child of children) {
            if (this.compareFingerprint(fingerprint, this.getStructureFingerprint(child)) > 0.8) {
                similar.push(child);
            }
        }
        
        return {
            selector: this.generateStructureSelector(element, parent),
            elements: similar,
            score: similar.length > 1 ? 0.9 : 0
        };
    }
    
    /**
     * 获取元素的结构指纹（用于比较）
     */
    getStructureFingerprint(element) {
        return {
            tag: element.tagName,
            depth: this.getDepth(element),
            childTags: Array.from(element.children).map(c => c.tagName),
            hasText: element.textContent.trim().length > 0,
            hasImage: element.querySelector('img') !== null,
            hasLink: element.querySelector('a') !== null,
            attributes: Array.from(element.attributes).map(a => a.name).sort()
        };
    }
    
    /**
     * 策略3: 视觉模式识别（位置、大小、样式）
     */
    strategyByVisualPattern(element) {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        
        // 视觉特征
        const visualFeatures = {
            width: Math.round(rect.width / 10) * 10,  // 近似宽度
            height: Math.round(rect.height / 10) * 10, // 近似高度
            display: style.display,
            float: style.float,
            position: style.position
        };
        
        // 查找视觉上相似的元素
        const allElements = document.querySelectorAll('*');
        const similar = [];
        
        for (const el of allElements) {
            if (el === element) continue;
            if (this.compareVisualFeatures(visualFeatures, el) > 0.85) {
                similar.push(el);
            }
        }
        
        // 过滤出合理的结果
        const filtered = this.filterByProximity(similar);
        
        return {
            elements: filtered,
            score: filtered.length > 2 ? 0.75 : 0,
            selector: this.generateVisualSelector(filtered)
        };
    }
    
    /**
     * 计算匹配分数
     */
    calculateScore(original, candidates) {
        const factors = {
            count: candidates.length > 2 && candidates.length < 50 ? 0.3 : 0,
            uniformity: this.checkUniformity(candidates) ? 0.3 : 0,
            layout: this.checkLayout(candidates) ? 0.2 : 0,
            content: this.checkContentSimilarity(candidates) ? 0.2 : 0
        };
        
        return Object.values(factors).reduce((a, b) => a + b, 0);
    }
    
    /**
     * 可视化展示建议
     */
    visualizeSuggestion(match) {
        if (!match || match.score < 0.5) {
            return this.fallbackToManualSelection();
        }
        
        // 高亮所有匹配元素
        match.elements.forEach((el, index) => {
            el.style.outline = '2px solid #4CAF50';
            el.style.outlineOffset = '2px';
            
            // 添加序号标签
            const label = document.createElement('div');
            label.className = 'smart-select-label';
            label.textContent = index + 1;
            label.style.cssText = `
                position: absolute;
                background: #4CAF50;
                color: white;
                padding: 2px 6px;
                border-radius: 10px;
                font-size: 12px;
                z-index: 10000;
            `;
            el.style.position = 'relative';
            el.appendChild(label);
        });
        
        return {
            success: true,
            count: match.elements.length,
            selector: match.selector,
            elements: match.elements,
            confidence: match.score
        };
    }
}