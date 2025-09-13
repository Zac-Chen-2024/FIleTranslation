import React, { useState, useRef } from 'react';
import { useApp } from '../../contexts/AppContext';
import { materialAPI } from '../../services/api';
// import UploadProgressModal from './UploadProgressModal'; // 改用全局进度弹窗
import styles from './Modal.module.css';

const AddMaterialModal = () => {
  const { state, actions } = useApp();
  const { modals, currentClient, uploadStatus } = state;
  const isUploading = uploadStatus.isUploading;
  const [uploadMethod, setUploadMethod] = useState('');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [urls, setUrls] = useState('');
  const [loading, setLoading] = useState(false);
  // 使用全局上传状态，移除本地上传状态
  // const [uploadProgress, setUploadProgress] = useState({ current: 0, total: 0, message: '' });
  // const [isUploading, setIsUploading] = useState(false);
  // const [showProgressModal, setShowProgressModal] = useState(false);
  
  // 文件输入的引用
  const fileInputRef = useRef(null);
  const folderInputRef = useRef(null);

  const handleClose = () => {
    actions.toggleModal('addMaterial', false);
    resetForm();
  };

  const resetForm = () => {
    setUploadMethod('');
    setSelectedFiles([]);
    setUrls('');
    setLoading(false);
    // 已移除本地上传状态，使用全局状态
    // setUploadProgress({ current: 0, total: 0, message: '' });
    // setIsUploading(false);
    // setShowProgressModal(false);
  };

  const handleMethodSelect = (method) => {
    setUploadMethod(method);
    setSelectedFiles([]);
    setUrls('');
    
    // 直接触发文件选择
    setTimeout(() => {
      if (method === 'file' && fileInputRef.current) {
        fileInputRef.current.click();
      } else if (method === 'folder' && folderInputRef.current) {
        folderInputRef.current.click();
      }
    }, 100);
  };

  const handleFileSelect = (event, isFolder = false) => {
    const files = Array.from(event.target.files);
    setSelectedFiles(files);
  };

  const handleUrlsChange = (event) => {
    setUrls(event.target.value);
  };

  const getFileType = (filename) => {
    const ext = filename.split('.').pop().toLowerCase();
    if (['pdf'].includes(ext)) return 'pdf';
    if (['jpg', 'jpeg', 'png', 'bmp', 'gif', 'tiff'].includes(ext)) return 'image';
    return 'document';
  };

  const handleSubmit = async () => {
    if (!currentClient) {
      actions.showNotification('错误', '没有选择客户', 'error');
      return;
    }

    let materialsToAdd = [];
    let apiCall = null;

    if (uploadMethod === 'file' || uploadMethod === 'folder') {
      if (selectedFiles.length === 0) {
        actions.showNotification('添加失败', '请选择文件', 'error');
        return;
      }

      materialsToAdd = selectedFiles.map(file => ({
        id: 'material_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
        clientId: currentClient.cid,
        name: uploadMethod === 'folder' ? file.webkitRelativePath || file.name : file.name,
        type: getFileType(file.name),
        status: '上传中',
        confirmed: false,
        file: file,
        createdAt: new Date().toISOString()
      }));

      // 准备文件上传API调用
      apiCall = () => materialAPI.uploadFiles(currentClient.cid, selectedFiles);

    } else if (uploadMethod === 'url') {
      if (!urls.trim()) {
        actions.showNotification('添加失败', '请输入网址', 'error');
        return;
      }

      const urlList = urls.trim().split('\n').filter(url => url.trim());
      materialsToAdd = urlList.map(url => ({
        id: 'material_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9),
        clientId: currentClient.cid,
        name: url.trim(),
        type: 'webpage',
        status: '添加中',
        confirmed: false,
        url: url.trim(),
        createdAt: new Date().toISOString()
      }));

      // 准备URL添加API调用
      apiCall = () => materialAPI.uploadUrls(currentClient.cid, urlList);
    }

    if (materialsToAdd.length === 0) {
      actions.showNotification('添加失败', '请选择文件或输入网址', 'error');
      return;
    }

    // 开始上传过程
    setLoading(true);

    // 启动全局上传进度
    actions.startUpload(materialsToAdd, '准备上传文件...');

    // 关闭添加材料弹窗
    actions.toggleModal('addMaterial', false);

    try {
      // 显示准备上传状态
      actions.updateUploadProgress(
        0, 
        '准备上传文件...', 
        true
      );

      // 先调用实际API，在等待过程中显示进度
      if (apiCall) {
        try {
          // 开始真正的上传，同时显示进度动画
          const uploadPromise = apiCall();
          
          // 在上传过程中显示动画进度
          const calculateDelay = (fileCount) => {
            if (fileCount === 1) return 300; // 单文件较快的动画
            if (fileCount <= 3) return 500; // 少量文件
            return Math.max(300, Math.min(800, fileCount * 300)); // 多文件
          };
          
          const delayPerFile = calculateDelay(materialsToAdd.length);
          
          // 显示上传进度动画（与真实上传并行）
          for (let i = 0; i < materialsToAdd.length; i++) {
            actions.updateUploadProgress(
              i + 1, 
              `正在上传: ${materialsToAdd[i].name}`,
              false // 上传过程中不能取消
            );
            await new Promise(resolve => setTimeout(resolve, delayPerFile));
          }
          
          // 等待真实上传完成
          actions.updateUploadProgress(
            materialsToAdd.length, 
            '等待服务器确认...', 
            false
          );
          
          const response = await uploadPromise;
          console.log('API响应:', response);
          
          // 使用API返回的实际材料数据
          if (response.materials) {
            actions.addMaterials(response.materials);
            
            // 保存上传的材料ID列表，用于后续的撤销功能
            const uploadedMaterialIds = response.materials.map(m => m.id);
            actions.setUploadedMaterials(uploadedMaterialIds);
          } else {
            // 如果API没有返回materials，使用本地数据
            const finalMaterials = materialsToAdd.map(material => ({
              ...material,
              status: '已添加'
            }));
            actions.addMaterials(finalMaterials);
          }
        } catch (apiError) {
          console.error('API调用错误:', apiError);
          // 网络错误时，先添加到本地，但标记为待同步
          const finalMaterials = materialsToAdd.map(material => ({
            ...material,
            status: '待同步'
          }));
          actions.addMaterials(finalMaterials);
          throw new Error(`网络连接失败: ${apiError.message}`);
        }
      } else {
        // 没有API调用的情况
        const finalMaterials = materialsToAdd.map(material => ({
          ...material,
          status: '已添加'
        }));
        actions.addMaterials(finalMaterials);
      }
      
      actions.showNotification('添加成功', `成功添加 ${materialsToAdd.length} 个材料`, 'success');
      
      // 显示最终完成状态
      actions.updateUploadProgress(
        materialsToAdd.length, 
        '上传完成！', 
        false, // canCancel = false
        false  // isUploading = false，允许再次上传
      );
      
      setLoading(false);
      
      // 重置表单
      resetForm();
      
    } catch (error) {
      actions.showNotification('添加失败', error.message || '添加材料时出现错误', 'error');
      actions.cancelUpload();
      setLoading(false);
      resetForm();
    }
  };


  const canSubmit = () => {
    if (uploadMethod === 'file' || uploadMethod === 'folder') {
      return selectedFiles.length > 0;
    }
    if (uploadMethod === 'url') {
      return urls.trim().length > 0;
    }
    return false;
  };

  if (!modals.addMaterial) return null;

  return (
    <div className={styles.overlay} onClick={handleClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h3 className={styles.title}>添加材料</h3>
          <button className={styles.closeBtn} onClick={handleClose}>
            &times;
          </button>
        </div>
        
        <div className={styles.body}>
          <div className={styles.uploadMethods}>
            <div 
              className={`${styles.uploadMethod} ${uploadMethod === 'file' ? styles.active : ''}`}
              onClick={() => handleMethodSelect('file')}
            >
              <div className={styles.uploadIcon}>📁</div>
              <h4 className={styles.uploadTitle}>文件上传</h4>
              <p className={styles.uploadDescription}>选择单个或多个文件进行上传</p>
            </div>
            
            <div 
              className={`${styles.uploadMethod} ${uploadMethod === 'folder' ? styles.active : ''}`}
              onClick={() => handleMethodSelect('folder')}
            >
              <div className={styles.uploadIcon}>📂</div>
              <h4 className={styles.uploadTitle}>文件夹上传</h4>
              <p className={styles.uploadDescription}>选择整个文件夹进行批量上传</p>
            </div>
            
            <div 
              className={`${styles.uploadMethod} ${uploadMethod === 'url' ? styles.active : ''}`}
              onClick={() => handleMethodSelect('url')}
            >
              <div className={styles.uploadIcon}>🌐</div>
              <h4 className={styles.uploadTitle}>网址粘贴</h4>
              <p className={styles.uploadDescription}>直接粘贴网址进行翻译</p>
            </div>
          </div>
          

          {/* 隐藏的文件输入 */}
          <input
            type="file"
            multiple
            style={{ display: 'none' }}
            onChange={(e) => handleFileSelect(e, false)}
            ref={fileInputRef}
          />
          
          <input
            type="file"
            webkitdirectory="true"
            style={{ display: 'none' }}
            onChange={(e) => handleFileSelect(e, true)}
            ref={folderInputRef}
          />
          
          {uploadMethod === 'url' && (
            <div className={styles.formGroup}>
              <label className={styles.label}>网址列表</label>
              <textarea
                className={styles.textarea}
                placeholder="请粘贴网址，每行一个：&#10;https://example1.com&#10;https://example2.com&#10;...&#10;&#10;或者您也可以将网址保存到 Address.txt 文件中，然后通过文件上传功能导入"
                value={urls}
                onChange={handleUrlsChange}
              />
            </div>
          )}
          

          {selectedFiles.length > 0 && !isUploading && (
            <div className={styles.selectedFiles}>
              <h4>已选择的文件：</h4>
              <div className={styles.filesList}>
                {selectedFiles.map((file, index) => (
                  <div key={index} className={styles.fileItem}>
                    <div className={styles.fileName}>{file.name}</div>
                    <div className={styles.fileSize}>
                      {(file.size / 1024).toFixed(2)} KB
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        
        <div className={styles.footer}>
          <button 
            className={`${styles.btn} ${styles.btnSecondary}`}
            onClick={handleClose}
            disabled={loading || isUploading}
          >
            {isUploading ? '上传中...' : '取消'}
          </button>
          <button 
            className={`${styles.btn} ${styles.btnPrimary}`}
            onClick={handleSubmit}
            disabled={!canSubmit() || loading || isUploading}
          >
            {isUploading 
              ? `上传中 ${uploadStatus.current}/${uploadStatus.total}` 
              : loading 
                ? '处理中...' 
                : '确认添加'
            }
          </button>
        </div>
      </div>
      
      {/* 独立的上传进度弹窗 */}
        {/* 全局上传进度弹窗将自动显示，无需在这里渲染 */}
    </div>
  );
};

export default AddMaterialModal;





