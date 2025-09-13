import React, { useState, useEffect } from 'react';
import { useApp } from '../../contexts/AppContext';
import { materialAPI } from '../../services/api';
import styles from './LaTeXEditModal.module.css';

const LaTeXEditModal = ({ isOpen, onClose, material }) => {
  const { actions } = useApp();
  const [editMode, setEditMode] = useState('description'); // 'description' | 'code'
  const [description, setDescription] = useState('');
  const [latexCode, setLatexCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [currentHistoryIndex, setCurrentHistoryIndex] = useState(-1);

  // 模拟的LaTeX代码
  const mockLatexCode = `\\documentclass{article}
\\usepackage[utf8]{inputenc}
\\usepackage{graphicx}
\\usepackage{booktabs}
\\usepackage{xeCJK}

\\title{翻译文档}
\\author{智能翻译平台}
\\date{\\today}

\\begin{document}

\\maketitle

\\section{文档内容}

这是一个示例LaTeX文档，展示了翻译后的内容。

\\begin{table}[h]
\\centering
\\begin{tabular}{@{}lll@{}}
\\toprule
项目 & 描述 & 状态 \\\\
\\midrule
文档翻译 & PDF格式翻译 & 完成 \\\\
图片识别 & OCR文字识别 & 进行中 \\\\
\\bottomrule
\\end{tabular}
\\caption{翻译进度表}
\\end{table}

\\section{总结}

翻译工作已按计划进行。

\\end{document}`;

  useEffect(() => {
    if (isOpen && material) {
      // 初始化LaTeX代码（实际应该从后端获取）
      setLatexCode(mockLatexCode);
      setDescription('');
      
      // 初始化历史记录
      const initialHistory = [{
        timestamp: new Date().toISOString(),
        description: '初始版本',
        code: mockLatexCode
      }];
      setHistory(initialHistory);
      setCurrentHistoryIndex(0);
    }
  }, [isOpen, material]);

  const handleClose = () => {
    setEditMode('description');
    setDescription('');
    setLatexCode('');
    setHistory([]);
    setCurrentHistoryIndex(-1);
    onClose();
  };

  const handleDescriptionEdit = async () => {
    if (!description.trim()) {
      actions.showNotification('请输入修改描述', '请描述您要修改的内容', 'warning');
      return;
    }

    setLoading(true);
    try {
      // 模拟AI生成新的LaTeX代码
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // 模拟代码修改
      const newCode = latexCode.replace(
        '翻译工作已按计划进行。',
        '翻译工作已按计划进行。\\n\\n根据用户要求：' + description + '\\n已完成相应修改。'
      );
      
      // 添加到历史记录
      const newHistoryItem = {
        timestamp: new Date().toISOString(),
        description: description,
        code: newCode
      };
      
      const newHistory = [...history, newHistoryItem];
      setHistory(newHistory);
      setCurrentHistoryIndex(newHistory.length - 1);
      setLatexCode(newCode);
      setDescription('');
      
      actions.showNotification('编辑完成', 'LaTeX代码已根据您的描述更新', 'success');
      
      // 实际API调用
      // const result = await materialAPI.editLatex(material.id, description);
      // setLatexCode(result.latexCode);
      
    } catch (error) {
      actions.showNotification('编辑失败', error.message || '编辑过程中出现错误', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleCodeEdit = () => {
    if (latexCode.trim() === (history[currentHistoryIndex]?.code || '')) {
      actions.showNotification('没有修改', '代码内容没有变化', 'warning');
      return;
    }

    // 添加到历史记录
    const newHistoryItem = {
      timestamp: new Date().toISOString(),
      description: '手动编辑代码',
      code: latexCode
    };
    
    const newHistory = [...history, newHistoryItem];
    setHistory(newHistory);
    setCurrentHistoryIndex(newHistory.length - 1);
    
    actions.showNotification('保存成功', '代码修改已保存', 'success');
  };

  const handleHistorySelect = (index) => {
    setCurrentHistoryIndex(index);
    setLatexCode(history[index].code);
  };

  const handleApply = () => {
    // 应用当前的LaTeX代码到材料
    actions.updateMaterial(material.id, { 
      latexCode: latexCode,
      lastModified: new Date().toISOString()
    });
    
    actions.showNotification('应用成功', 'LaTeX代码已应用到材料', 'success');
    handleClose();
  };

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={handleClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h3 className={styles.title}>
            LaTeX 编辑器 - {material?.name}
          </h3>
          <button className={styles.closeBtn} onClick={handleClose}>
            &times;
          </button>
        </div>

        <div className={styles.toolbar}>
          <div className={styles.modeSwitch}>
            <button 
              className={`${styles.modeBtn} ${editMode === 'description' ? styles.active : ''}`}
              onClick={() => setEditMode('description')}
            >
              🤖 AI编辑
            </button>
            <button 
              className={`${styles.modeBtn} ${editMode === 'code' ? styles.active : ''}`}
              onClick={() => setEditMode('code')}
            >
              📝 代码编辑
            </button>
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
          <div className={styles.leftPanel}>
            {editMode === 'description' ? (
              <div className={styles.descriptionMode}>
                <h4 className={styles.panelTitle}>描述修改内容</h4>
                <textarea
                  className={styles.descriptionInput}
                  placeholder="请用自然语言描述您要修改的内容，例如：&#10;- 将表格第二行字体放大&#10;- 添加一个新的章节&#10;- 修改标题颜色为蓝色&#10;- 调整页面边距"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
                <button 
                  className={`${styles.btn} ${styles.btnSuccess}`}
                  onClick={handleDescriptionEdit}
                  disabled={loading || !description.trim()}
                >
                  {loading ? '🤖 AI生成中...' : '🚀 生成修改'}
                </button>
              </div>
            ) : (
              <div className={styles.codeMode}>
                <div className={styles.codeHeader}>
                  <h4 className={styles.panelTitle}>LaTeX 代码</h4>
                  <button 
                    className={`${styles.btn} ${styles.btnSecondary}`}
                    onClick={handleCodeEdit}
                  >
                    保存修改
                  </button>
                </div>
                <textarea
                  className={styles.codeEditor}
                  value={latexCode}
                  onChange={(e) => setLatexCode(e.target.value)}
                  placeholder="在此编辑LaTeX代码..."
                />
              </div>
            )}
          </div>

          <div className={styles.rightPanel}>
            <h4 className={styles.panelTitle}>修改历史</h4>
            <div className={styles.historyList}>
              {history.map((item, index) => (
                <div 
                  key={index}
                  className={`${styles.historyItem} ${
                    index === currentHistoryIndex ? styles.active : ''
                  }`}
                  onClick={() => handleHistorySelect(index)}
                >
                  <div className={styles.historyHeader}>
                    <span className={styles.historyIndex}>#{index + 1}</span>
                    <span className={styles.historyTime}>
                      {new Date(item.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className={styles.historyDescription}>
                    {item.description}
                  </div>
                </div>
              ))}
            </div>
            
            <div className={styles.previewSection}>
              <h4 className={styles.panelTitle}>预览</h4>
              <div className={styles.preview}>
                <div className={styles.previewPlaceholder}>
                  <div className="loading-spinner"></div>
                  <p>LaTeX 编译预览</p>
                  <small>实际项目中这里会显示PDF预览</small>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LaTeXEditModal;




