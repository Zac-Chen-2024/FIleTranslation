import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useApp } from '../../contexts/AppContext';
import { materialAPI } from '../../services/api';
import styles from './LaTeXEditModalV2.module.css';

const LaTeXEditModalV2 = ({ isOpen, onClose, material }) => {
  const { actions } = useApp();
  const [latexCode, setLatexCode] = useState('');
  const [selectedText, setSelectedText] = useState('');
  const [selectedCodeRange, setSelectedCodeRange] = useState(null);
  const [editDescription, setEditDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [previewElements, setPreviewElements] = useState([]);
  const [hoveredElement, setHoveredElement] = useState(null);
  const [editHistory, setEditHistory] = useState([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [pdfScale, setPdfScale] = useState(1);
  
  const previewRef = useRef(null);
  const codeEditorRef = useRef(null);
  const lineNumbersRef = useRef(null);

  // 模拟的LaTeX代码，包含行号和内容的映射
  const mockLatexCode = `\\documentclass{article}
\\usepackage[utf8]{inputenc}
\\usepackage{graphicx}
\\usepackage{booktabs}
\\usepackage{xeCJK}

\\title{智能法律文书翻译}
\\author{法律翻译平台}
\\date{\\today}

\\begin{document}

\\maketitle

\\section{合同条款}
\\label{sec:contract}

本合同由甲方与乙方于2024年签署，具体条款如下：

\\subsection{第一条：基本信息}
\\begin{itemize}
\\item 甲方：北京律师事务所
\\item 乙方：上海科技公司  
\\item 签署日期：2024年1月15日
\\end{itemize}

\\subsection{第二条：权利义务}

\\begin{table}[h]
\\centering
\\begin{tabular}{@{}lll@{}}
\\toprule
项目 & 甲方义务 & 乙方义务 \\\\
\\midrule
法律咨询 & 提供专业意见 & 配合调查 \\\\
费用支付 & 按时收费 & 按时付款 \\\\
保密义务 & 保护客户隐私 & 保护商业机密 \\\\
\\bottomrule
\\end{tabular}
\\caption{权利义务对照表}
\\label{tab:obligations}
\\end{table}

\\section{争议解决}

如发生争议，双方应通过以下方式解决：
\\begin{enumerate}
\\item 协商解决
\\item 调解解决  
\\item 仲裁解决
\\item 诉讼解决
\\end{enumerate}

\\section{附加条款}

\\textbf{重要提醒：}本合同一式两份，甲乙双方各执一份。

\\vspace{1cm}

\\noindent
甲方签字：\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_

\\noindent  
乙方签字：\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_\\_

\\end{document}`;

  // 模拟的预览元素，每个元素对应LaTeX代码的某个范围
  const mockPreviewElements = [
    {
      id: 'title',
      text: '智能法律文书翻译',
      type: 'title',
      latexRange: { start: 7, end: 7 }, // 第7行的\title
      boundingBox: { top: 20, left: 50, width: 300, height: 40 }
    },
    {
      id: 'author',
      text: '法律翻译平台',
      type: 'author',
      latexRange: { start: 8, end: 8 },
      boundingBox: { top: 70, left: 80, width: 200, height: 25 }
    },
    {
      id: 'section1',
      text: '合同条款',
      type: 'section',
      latexRange: { start: 15, end: 15 },
      boundingBox: { top: 120, left: 30, width: 150, height: 30 }
    },
    {
      id: 'contract_content',
      text: '本合同由甲方与乙方于2024年签署，具体条款如下：',
      type: 'text',
      latexRange: { start: 18, end: 18 },
      boundingBox: { top: 160, left: 30, width: 400, height: 25 }
    },
    {
      id: 'subsection1',
      text: '第一条：基本信息',
      type: 'subsection',
      latexRange: { start: 20, end: 20 },
      boundingBox: { top: 200, left: 40, width: 180, height: 25 }
    },
    {
      id: 'itemize_content',
      text: '• 甲方：北京律师事务所\n• 乙方：上海科技公司\n• 签署日期：2024年1月15日',
      type: 'itemize',
      latexRange: { start: 21, end: 25 },
      boundingBox: { top: 235, left: 50, width: 350, height: 75 }
    },
    {
      id: 'subsection2',
      text: '第二条：权利义务',
      type: 'subsection',
      latexRange: { start: 27, end: 27 },
      boundingBox: { top: 330, left: 40, width: 180, height: 25 }
    },
    {
      id: 'table',
      text: '权利义务对照表\n项目 | 甲方义务 | 乙方义务\n法律咨询 | 提供专业意见 | 配合调查\n费用支付 | 按时收费 | 按时付款\n保密义务 | 保护客户隐私 | 保护商业机密',
      type: 'table',
      latexRange: { start: 29, end: 39 },
      boundingBox: { top: 370, left: 30, width: 450, height: 120 }
    },
    {
      id: 'section2',
      text: '争议解决',
      type: 'section',
      latexRange: { start: 43, end: 43 },
      boundingBox: { top: 510, left: 30, width: 120, height: 30 }
    },
    {
      id: 'enumerate_content',
      text: '1. 协商解决\n2. 调解解决\n3. 仲裁解决\n4. 诉讼解决',
      type: 'enumerate',
      latexRange: { start: 46, end: 51 },
      boundingBox: { top: 550, left: 50, width: 200, height: 100 }
    },
    {
      id: 'section3',
      text: '附加条款',
      type: 'section',
      latexRange: { start: 53, end: 53 },
      boundingBox: { top: 670, left: 30, width: 120, height: 30 }
    },
    {
      id: 'important_text',
      text: '重要提醒：本合同一式两份，甲乙双方各执一份。',
      type: 'text',
      latexRange: { start: 55, end: 55 },
      boundingBox: { top: 710, left: 30, width: 400, height: 25 }
    },
    {
      id: 'signatures',
      text: '甲方签字：_______________\n乙方签字：_______________',
      type: 'signature',
      latexRange: { start: 59, end: 62 },
      boundingBox: { top: 760, left: 30, width: 300, height: 50 }
    }
  ];

  useEffect(() => {
    if (isOpen && material) {
      setLatexCode(mockLatexCode);
      setPreviewElements(mockPreviewElements);
      setSelectedText('');
      setSelectedCodeRange(null);
      setEditDescription('');
      setEditHistory([
        {
          id: 1,
          timestamp: new Date().toISOString(),
          description: '初始版本',
          changes: '文档创建',
          user: '系统'
        }
      ]);
      setCurrentMessage('');
    }
  }, [isOpen, material]);

  const handleClose = () => {
    setLatexCode('');
    setSelectedText('');
    setSelectedCodeRange(null);
    setEditDescription('');
    setPreviewElements([]);
    setEditHistory([]);
    setCurrentMessage('');
    setHoveredElement(null);
    onClose();
  };

  // 处理PDF预览元素的悬停
  const handleElementHover = useCallback((element) => {
    setHoveredElement(element);
    
    // 悬停时滚动LaTeX代码，将对应代码块的第一行滚动到编辑器顶部
    if (codeEditorRef.current && element) {
      const lineHeight = 18; // 代码行高度
      const targetLine = element.latexRange.start;
      const codeLines = latexCode.split('\n');
      const totalLines = codeLines.length;
      const editorHeight = codeEditorRef.current.clientHeight;
      const padding = 16; // 1rem padding
      const visibleLines = Math.floor((editorHeight - padding * 2) / lineHeight);
      
      // 计算滚动位置：将目标行滚动到顶部
      let scrollTop = (targetLine - 1) * lineHeight;
      
      // 如果接近文档尾部，不能继续上拖时，滚动到尽量上的位置
      const maxScrollTop = Math.max(0, (totalLines - visibleLines) * lineHeight);
      scrollTop = Math.min(scrollTop, maxScrollTop);
      
      // 确保不小于0
      scrollTop = Math.max(0, scrollTop);
      
      // 调试信息
      console.log('Hover scroll to top:', {
        targetLine,
        totalLines,
        visibleLines,
        maxScrollTop,
        scrollTop,
        lineRange: `${element.latexRange.start}-${element.latexRange.end}`,
        highlightTop: (element.latexRange.start - 1) * 18,
        highlightHeight: (element.latexRange.end - element.latexRange.start + 1) * 18
      });
      
      codeEditorRef.current.scrollTop = scrollTop;
      // 同步行号区域的滚动
      if (lineNumbersRef.current) {
        lineNumbersRef.current.scrollTop = scrollTop;
      }
    }
  }, [latexCode]);

  // 处理PDF预览元素的点击 - 居中显示对应代码
  const handleElementClick = (element) => {
    setSelectedText(element.text);
    setSelectedCodeRange(element.latexRange);
    
    // 滚动LaTeX代码，将对应代码块的第一行滚动到编辑器顶部
    if (codeEditorRef.current && element) {
      const lineHeight = 18; // 代码行高度
      const targetLine = element.latexRange.start;
      const codeLines = latexCode.split('\n');
      const totalLines = codeLines.length;
      const editorHeight = codeEditorRef.current.clientHeight;
      const padding = 16; // 1rem padding
      const visibleLines = Math.floor((editorHeight - padding * 2) / lineHeight);
      
      // 计算滚动位置：将目标行滚动到顶部
      let scrollTop = (targetLine - 1) * lineHeight;
      
      // 如果接近文档尾部，不能继续上拖时，滚动到尽量上的位置
      const maxScrollTop = Math.max(0, (totalLines - visibleLines) * lineHeight);
      scrollTop = Math.min(scrollTop, maxScrollTop);
      
      // 确保不小于0
      scrollTop = Math.max(0, scrollTop);
      
      codeEditorRef.current.scrollTop = scrollTop;
      // 同步行号区域的滚动
      if (lineNumbersRef.current) {
        lineNumbersRef.current.scrollTop = scrollTop;
      }
    }
    
    // 移除选中内容的通知提醒
  };

  // 处理LaTeX代码的悬停
  const handleCodeHover = useCallback((lineNumber) => {
    const correspondingElement = previewElements.find(
      element => lineNumber >= element.latexRange.start && lineNumber <= element.latexRange.end
    );
    
    if (correspondingElement) {
      setHoveredElement(correspondingElement);
    }
  }, [previewElements]);

  // 发送消息
  const handleSendMessage = async () => {
    if (!currentMessage.trim()) return;
    
    setLoading(true);
    try {
      // 添加用户消息到历史
      const userMessage = {
        id: Date.now(),
        timestamp: new Date().toISOString(),
        description: currentMessage,
        changes: selectedText ? `修改选中内容: "${selectedText.substring(0, 30)}..."` : '全局修改',
        user: '用户'
      };
      
      setEditHistory(prev => [...prev, userMessage]);
      
      // 模拟AI处理
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // 模拟AI响应
      const aiResponse = {
        id: Date.now() + 1,
        timestamp: new Date().toISOString(),
        description: '已完成修改',
        changes: `根据指令"${currentMessage}"完成LaTeX代码修改`,
        user: 'AI助手'
      };
      
      setEditHistory(prev => [...prev, aiResponse]);
      setCurrentMessage('');
      
      actions.showNotification('修改完成', 'AI已根据您的指令完成修改', 'success');
      
    } catch (error) {
      actions.showNotification('修改失败', error.message || '处理过程中出现错误', 'error');
    } finally {
      setLoading(false);
    }
  };

  // PDF缩放控制
  const handleZoomIn = () => {
    setPdfScale(prev => Math.min(prev + 0.2, 3));
  };

  const handleZoomOut = () => {
    setPdfScale(prev => Math.max(prev - 0.2, 0.5));
  };

  const handleZoomReset = () => {
    setPdfScale(1);
  };

  // 处理代码编辑器滚动，同步行号区域
  const handleCodeScroll = () => {
    if (codeEditorRef.current && lineNumbersRef.current) {
      lineNumbersRef.current.scrollTop = codeEditorRef.current.scrollTop;
    }
  };

  // 处理针对选中代码的编辑
  const handleTargetedEdit = async () => {
    if (!selectedCodeRange || !editDescription.trim()) {
      actions.showNotification('请选择内容并输入修改描述', '需要先选中预览内容，然后描述修改需求', 'warning');
      return;
    }

    setLoading(true);
    try {
      // 模拟AI处理选中的代码段
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const codeLines = latexCode.split('\n');
      const { start, end } = selectedCodeRange;
      
      // 模拟修改选中的代码段
      let modifiedLines = [...codeLines];
      const originalLines = codeLines.slice(start - 1, end);
      
      // 简单的修改逻辑示例
      if (editDescription.includes('加粗') || editDescription.includes('粗体')) {
        for (let i = start - 1; i < end; i++) {
          if (modifiedLines[i] && !modifiedLines[i].includes('\\textbf{')) {
            modifiedLines[i] = modifiedLines[i].replace(/([^\\]+)$/, '\\textbf{$1}');
          }
        }
      } else if (editDescription.includes('颜色') || editDescription.includes('红色')) {
        modifiedLines.splice(start - 1, 0, '\\usepackage{xcolor}');
        for (let i = start; i < end + 1; i++) {
          if (modifiedLines[i] && !modifiedLines[i].includes('\\textcolor{')) {
            modifiedLines[i] = modifiedLines[i].replace(/([^\\]+)$/, '\\textcolor{red}{$1}');
          }
        }
      } else if (editDescription.includes('字体') || editDescription.includes('大小')) {
        for (let i = start - 1; i < end; i++) {
          if (modifiedLines[i] && !modifiedLines[i].includes('\\large')) {
            modifiedLines[i] = modifiedLines[i].replace(/([^\\]+)$/, '\\large{$1}');
          }
        }
      } else {
        // 通用修改：在选中内容后添加注释
        modifiedLines.splice(end, 0, `% 用户修改: ${editDescription}`);
      }
      
      const newLatexCode = modifiedLines.join('\n');
      setLatexCode(newLatexCode);
      
      actions.showNotification(
        '修改完成', 
        `已根据"${editDescription}"修改了选中的LaTeX代码`, 
        'success'
      );
      
      setEditDescription('');
      
      // 实际API调用
      // const result = await materialAPI.editSelectedLatex(material.id, selectedCodeRange, editDescription);
      // setLatexCode(result.latexCode);
      
    } catch (error) {
      actions.showNotification('修改失败', error.message || '修改过程中出现错误', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = () => {
    actions.updateMaterial(material.id, { 
      latexCode: latexCode,
      lastModified: new Date().toISOString()
    });
    
    actions.showNotification('应用成功', 'LaTeX代码已应用到材料', 'success');
    handleClose();
  };

  // 获取选中代码的内容
  const getSelectedCodeContent = () => {
    if (!selectedCodeRange) return '';
    const codeLines = latexCode.split('\n');
    return codeLines.slice(selectedCodeRange.start - 1, selectedCodeRange.end).join('\n');
  };

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={handleClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h3 className={styles.title}>
            🧪 LaTeX 编辑器 V2 (测试版) - {material?.name}
          </h3>
          <div className={styles.headerActions}>
            <span className={styles.badge}>实验功能</span>
            <button className={styles.closeBtn} onClick={handleClose}>
              &times;
            </button>
          </div>
        </div>

        <div className={styles.toolbar}>
          <div className={styles.toolbarInfo}>
            <span className={styles.infoText}>
              💡 点击右侧预览中的任何内容，然后在左侧输入修改指令
            </span>
          </div>
          <div className={styles.actions}>
            <button 
              className={`${styles.btn} ${styles.btnPrimary}`}
              onClick={handleApply}
            >
              应用修改
            </button>
          </div>
        </div>

        <div className={styles.body}>
          {/* 左侧：PDF预览 */}
          <div className={styles.leftPanel}>
            <div className={styles.panelHeader}>
              <h4 className={styles.sectionTitle}>PDF预览</h4>
              <div className={styles.zoomControls}>
                <button 
                  className={styles.zoomBtn}
                  onClick={handleZoomOut}
                  title="缩小"
                >
                  −
                </button>
                <span className={styles.zoomLevel}>{Math.round(pdfScale * 100)}%</span>
                <button 
                  className={styles.zoomBtn}
                  onClick={handleZoomIn}
                  title="放大"
                >
                  +
                </button>
                <button 
                  className={styles.zoomBtn}
                  onClick={handleZoomReset}
                  title="重置"
                >
                  ⌂
                </button>
              </div>
            </div>
            <div className={styles.pdfPreview} ref={previewRef}>
              <div 
                className={styles.pdfContent}
                style={{
                  transform: `scale(${pdfScale})`,
                  transformOrigin: 'top left',
                  width: `${100 / pdfScale}%`,
                  height: `${100 / pdfScale}%`
                }}
              >
                {previewElements.map((element) => (
                  <div
                    key={element.id}
                    className={`${styles.previewElement} ${styles[element.type]} ${
                      selectedCodeRange?.start === element.latexRange.start ? styles.selected : ''
                    } ${hoveredElement?.id === element.id ? styles.hovered : ''}`}
                    style={{
                      top: element.boundingBox.top,
                      left: element.boundingBox.left,
                      width: element.boundingBox.width,
                      height: element.boundingBox.height
                    }}
                    onClick={() => handleElementClick(element)}
                    onMouseEnter={() => handleElementHover(element)}
                    onMouseLeave={() => setHoveredElement(null)}
                    title={`第${element.latexRange.start}-${element.latexRange.end}行`}
                  >
                    {element.text.split('\n').map((line, index) => (
                      <div key={index} className={styles.previewLine}>
                        {line}
                      </div>
                    ))}
                    <div className={styles.elementOverlay}>
                      <span className={styles.elementLabel}>
                        {element.latexRange.start}-{element.latexRange.end}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 中间：LaTeX代码 */}
          <div className={styles.middlePanel}>
            <div className={styles.panelHeader}>
              <h4 className={styles.sectionTitle}>LaTeX代码</h4>
            </div>
            <div className={styles.codeContainer}>
              <div className={styles.codeEditorWrapper}>
                <div 
                  ref={lineNumbersRef}
                  className={styles.lineNumbers}
                >
                  {latexCode.split('\n').map((_, index) => (
                    <div 
                      key={index}
                      className={`${styles.lineNumber} ${
                        hoveredElement && 
                        index + 1 >= hoveredElement.latexRange.start && 
                        index + 1 <= hoveredElement.latexRange.end 
                          ? styles.highlighted : ''
                      }`}
                      onMouseEnter={() => handleCodeHover(index + 1)}
                    >
                      {index + 1}
                    </div>
                  ))}
                </div>
                <div className={styles.codeAreaWrapper}>
                  <textarea
                    ref={codeEditorRef}
                    className={styles.codeEditor}
                    value={latexCode}
                    onChange={(e) => setLatexCode(e.target.value)}
                    onScroll={handleCodeScroll}
                    placeholder="LaTeX代码将在这里显示..."
                  />
                  {/* 代码高光已移除，只保留行号高光 */}
                </div>
              </div>
            </div>
          </div>

          {/* 右侧：对话区域 */}
          <div className={styles.rightPanel}>
            <div className={styles.panelHeader}>
              <h4 className={styles.sectionTitle}>智能对话</h4>
            </div>
            
            {/* 当前选中信息 */}
            {selectedText && (
              <div className={styles.selectedInfo}>
                🎯 <strong>已选中：</strong>"{selectedText.substring(0, 30)}{selectedText.length > 30 ? '...' : ''}"
                <span className={styles.codeRange}>
                  (第{selectedCodeRange.start}-{selectedCodeRange.end}行)
                </span>
              </div>
            )}
            
            {/* 对话输入区 */}
            <div className={styles.chatInput}>
              <textarea
                className={styles.messageInput}
                placeholder="请描述您要的修改，例如：&#10;• 将标题改为红色&#10;• 在表格后添加一段总结&#10;• 调整页面边距"
                value={currentMessage}
                onChange={(e) => setCurrentMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    handleSendMessage();
                  }
                }}
              />
              <button 
                className={`${styles.btn} ${styles.btnSend}`}
                onClick={handleSendMessage}
                disabled={loading || !currentMessage.trim()}
                title="发送消息 (Ctrl+Enter)"
              >
                {loading ? '🤖' : '💫'}
              </button>
            </div>
            
            {/* 编辑历史 */}
            <div className={styles.editHistory}>
              <h5 className={styles.historyTitle}>编辑历史</h5>
              <div className={styles.historyList}>
                {editHistory.length === 0 ? (
                  <div className={styles.emptyHistory}>
                    <div className={styles.emptyHistoryText}>还没有对话记录</div>
                    <div className={styles.emptyHistorySubtext}>选择PDF内容并输入修改需求开始对话</div>
                  </div>
                ) : (
                  editHistory.map((item) => (
                    <div key={item.id} className={`${styles.historyItem} ${styles[item.user === 'AI助手' ? 'aiMessage' : 'userMessage']}`}>
                      <div className={styles.historyHeader}>
                        <span className={styles.historyUser}>{item.user}</span>
                        <span className={styles.historyTime}>
                          {new Date(item.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <div className={styles.historyDescription}>
                        {item.description}
                      </div>
                      <div className={styles.historyChanges}>
                        {item.changes}
                      </div>
                    </div>
                  ))
                )}
                
                {/* 加载状态 */}
                {loading && (
                  <div className={styles.loadingMessage}>
                    <div className={styles.loadingDots}>
                      <div className={styles.loadingDot}></div>
                      <div className={styles.loadingDot}></div>
                      <div className={styles.loadingDot}></div>
                    </div>
                    <div className={styles.loadingText}>AI正在思考中...</div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LaTeXEditModalV2;
