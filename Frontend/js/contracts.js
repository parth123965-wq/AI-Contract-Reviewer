/* =========================================================
   AI Contract Reviewer - Contracts Helper Module
========================================================= */

const ContractUtils = {
  formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  },

  getRiskCategory(score) {
    if (score === null || score === undefined) return { label: 'Unknown', color: 'muted' };
    if (score >= 70) return { label: 'High Risk', color: 'danger' };
    if (score >= 40) return { label: 'Medium Risk', color: 'warning' };
    return { label: 'Low Risk', color: 'success' };
  }
};