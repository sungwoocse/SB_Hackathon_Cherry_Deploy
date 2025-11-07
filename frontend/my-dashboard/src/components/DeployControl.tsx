'use client';
import { useState, useEffect } from 'react';
import {
  triggerDeploy,
  fetchDeployStatus,
  triggerRollback,
  fetchPreview,
} from '@/lib/api';
import { DeployResponse, DeployStatusResponse } from '@/types/deploy';

export default function DeployControl() {
  const [deployStatus, setDeployStatus] = useState<DeployStatusResponse | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<any>(null);

  // 배포 프리뷰 로드
  useEffect(() => {
    fetchPreview().then(setPreview).catch(console.error);
  }, []);

  // 배포 상태 주기적 확인
  useEffect(() => {
    if (!taskId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetchDeployStatus(taskId);
        setDeployStatus(res);
        if (res.status === 'completed' || res.status === 'failed') clearInterval(interval);
      } catch (err) {
        console.error(err);
        clearInterval(interval);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [taskId]);

  // 배포 실행
  const handleDeploy = async () => {
    setLoading(true);
    setError(null);
    try {
      const res: DeployResponse = await triggerDeploy({ branch: 'deploy' });
      setTaskId(res.task_id);
    } catch (err: any) {
      setError(err.message || '배포 요청 실패');
    } finally {
      setLoading(false);
    }
  };

  // 롤백 실행
  const handleRollback = async () => {
    if (!confirm('이전 버전으로 롤백하시겠습니까?')) return;
    setLoading(true);
    try {
      await triggerRollback({ branch: 'deploy' });
      alert('롤백 요청이 전송되었습니다.');
    } catch (err: any) {
      setError(err.message || '롤백 실패');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 bg-slate-800 rounded-2xl shadow-lg text-white">
      <h2 className="text-xl font-semibold mb-4">🚀 배포 제어</h2>

      <div className="mb-4">
        <button
          onClick={handleDeploy}
          disabled={loading}
          className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded mr-2"
        >
          {loading ? '배포 중...' : '배포 시작'}
        </button>
        <button
          onClick={handleRollback}
          disabled={loading}
          className="px-4 py-2 bg-red-600 hover:bg-red-500 rounded"
        >
          롤백
        </button>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {deployStatus && (
        <div className="mt-4 text-sm">
          <p>상태: <span className="font-semibold text-yellow-300">{deployStatus.status}</span></p>
          <p>시작: {new Date(deployStatus.started_at).toLocaleString()}</p>
          {deployStatus.completed_at && (
            <p>완료: {new Date(deployStatus.completed_at).toLocaleString()}</p>
          )}
          {deployStatus.error_log && (
            <pre className="mt-2 text-red-300 bg-slate-900 p-2 rounded text-xs overflow-auto">
              {deployStatus.error_log}
            </pre>
          )}
        </div>
      )}

      <div className="mt-6 border-t border-slate-600 pt-4">
        <h3 className="font-semibold mb-2">📋 배포 프리뷰</h3>
        {preview ? (
          <pre className="text-xs bg-slate-900 p-2 rounded overflow-auto max-h-48">
            {JSON.stringify(preview, null, 2)}
          </pre>
        ) : (
          <p className="text-gray-400 text-sm">불러오는 중...</p>
        )}
      </div>
    </div>
  );
}
