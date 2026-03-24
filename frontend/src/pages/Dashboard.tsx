import { useCallback, useState, useEffect } from 'react';
import { useJobs } from '../hooks/useJobs';
import { useWebSocket } from '../hooks/useWebSocket';
import { JobForm } from '../components/jobs/JobForm';
import { JobList } from '../components/jobs/JobList';
import { ToastContainer } from '../components/common/Toast';
import { Layout } from '../components/layout/Layout';
import { apiService } from '../services/api';
import type { WebSocketMessage, JobCreateRequest } from '../types';

interface DashboardProps {
  onLogout: () => void;
}

interface ToastItem {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
}

// localStorage helper functions for idempotency key management
const STORAGE_KEY_PREFIX = 'job_idempotency_pending';

function getPendingIdempotencyKey(): string | null {
  return localStorage.getItem(STORAGE_KEY_PREFIX);
}

function setPendingIdempotencyKey(key: string): void {
  localStorage.setItem(STORAGE_KEY_PREFIX, key);
}

function clearPendingIdempotencyKey(): void {
  localStorage.removeItem(STORAGE_KEY_PREFIX);
}

export function Dashboard({ onLogout }: DashboardProps) {
  // Get userId from JWT token
  const userId = apiService.getUserId() || 'unknown';

  const [toasts, setToasts] = useState<ToastItem[]>([]);
  
  const addToast = useCallback((message: string, type: ToastItem['type']) => {
    const id = Date.now().toString();
    setToasts(prev => [...prev, { id, message, type }]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const {
    jobs,
    total,
    page,
    pageSize,
    isLoading,
    error,
    createJob,
    updateJobLocally,
    fetchJobs,
    setPage,
  } = useJobs();

  const handleWsMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === 'job_update') {
      const statusEmoji: Record<string, string> = {
        PENDING: '⏳',
        PROCESSING: '🔄',
        COMPLETED: '✅',
        FAILED: '❌',
      };
      
      addToast(
        `Job ${message.data.job_id.slice(0, 8)}... actualizado: ${statusEmoji[message.data.status]} ${message.data.status}`,
        message.data.status === 'FAILED' ? 'error' : 'success'
      );
      
      // Update the specific job in the local list
      updateJobLocally(message.data.job_id, {
        status: message.data.status,
        result_url: message.data.result_url,
        updated_at: message.data.updated_at,
      });
    }
  }, [addToast, updateJobLocally]);

  const { isConnected, connect, disconnect } = useWebSocket(handleWsMessage);

  // Connect WebSocket when component mounts
  useEffect(() => {
    if (userId && userId !== 'unknown') {
      connect(userId);
    }
    return () => disconnect();
  }, [userId, connect, disconnect]);

  const handleCreateJob = async (data: { report_type: string; date_range: string; format: string }) => {
    const jobData: JobCreateRequest = {
      report_type: data.report_type,
      date_range: data.date_range,
      format: data.format as 'pdf' | 'csv' | 'excel',
    };
    
    // Check for pending idempotency key or generate new one
    let idempotencyKey = getPendingIdempotencyKey();
    if (!idempotencyKey) {
      idempotencyKey = crypto.randomUUID();
    }
    
    const result = await createJob(jobData, idempotencyKey);
    
    if (result.success) {
      // Clear pending key after successful creation
      clearPendingIdempotencyKey();
      
      if (result.idempotent) {
        addToast('Reporte recuperado exitosamente (petición idempotente)', 'info');
      } else {
        addToast('Reporte solicitado exitosamente', 'success');
      }
    } else {
      // Keep the key in storage for retry
      setPendingIdempotencyKey(idempotencyKey);
      addToast('Error al solicitar reporte', 'error');
    }
    return result.success;
  };

  return (
    <Layout userId={userId} onLogout={onLogout} wsConnected={isConnected}>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1">
          <JobForm onSubmit={handleCreateJob} isLoading={isLoading} />
        </div>
        
        <div className="lg:col-span-2">
          <JobList
            jobs={jobs}
            isLoading={isLoading}
            error={error}
            onRefresh={fetchJobs}
            page={page}
            pageSize={pageSize}
            total={total}
            onPageChange={setPage}
          />
        </div>
      </div>

      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </Layout>
  );
}
