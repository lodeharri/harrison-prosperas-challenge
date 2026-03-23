import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { apiService } from '../services/api';
import { JobBadge } from '../components/jobs/JobBadge';
import { Layout } from '../components/layout/Layout';
import { useWebSocket } from '../hooks/useWebSocket';
import { getReportTypeLabel } from '../reportTypes';
import type { Job, WebSocketMessage } from '../types';

export function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const userId = apiService.getUserId() || 'unknown';
  
  const [job, setJob] = useState<Job | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleWsMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === 'job_update' && message.data.job_id === id) {
      setJob(prev => prev ? { 
        ...prev, 
        status: message.data.status,
        result_url: message.data.result_url ?? null,
        updated_at: message.data.updated_at
      } : null);
    }
  }, [id]);

  const { isConnected, connect, disconnect } = useWebSocket(handleWsMessage);

  // Connect WebSocket and fetch job details
  useEffect(() => {
    if (!id) {
      setError('ID de job no proporcionado');
      setIsLoading(false);
      return;
    }

    const fetchJob = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await apiService.getJob(id);
        setJob(data);
      } catch (err) {
        setError('Error al cargar los detalles del job');
        console.error('Error fetching job:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchJob();

    // Connect WebSocket for real-time updates
    if (userId && userId !== 'unknown') {
      connect(userId);
    }

    return () => disconnect();
  }, [id, userId, connect, disconnect]);

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('es-ES', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatShortDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('es-ES');
  };

  if (isLoading) {
    return (
      <Layout userId={userId} onLogout={() => navigate('/')} wsConnected={isConnected}>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="flex flex-col items-center gap-4">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary-500 border-t-transparent"></div>
            <p className="text-gray-500">Cargando detalles del job...</p>
          </div>
        </div>
      </Layout>
    );
  }

  if (error || !job) {
    return (
      <Layout userId={userId} onLogout={() => navigate('/')} wsConnected={isConnected}>
        <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
          <div className="text-red-500 text-5xl">❌</div>
          <p className="text-gray-600">{error || 'Job no encontrado'}</p>
          <Link to="/" className="btn-primary">
            Volver a la lista
          </Link>
        </div>
      </Layout>
    );
  }

  return (
    <Layout userId={userId} onLogout={() => navigate('/')} wsConnected={isConnected}>
      <div className="max-w-3xl mx-auto">
        {/* Back Navigation */}
        <Link 
          to="/" 
          className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
          </svg>
          Volver a la lista de jobs
        </Link>

        {/* Header Card */}
        <div className="card mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{getReportTypeLabel(job.report_type)}</h1>
              <p className="text-sm text-gray-500 mt-1">ID: <span className="font-mono">{job.job_id}</span></p>
            </div>
            <JobBadge status={job.status} />
          </div>

          {/* Download Button for Completed Jobs */}
          {job.result_url && job.status === 'COMPLETED' && (
            <a
              href={job.result_url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary inline-flex items-center gap-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
              Descargar Reporte
            </a>
          )}
        </div>

        {/* Details Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Report Type */}
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Tipo de Reporte</h3>
            <p className="text-lg font-semibold text-gray-900">{getReportTypeLabel(job.report_type)}</p>
          </div>

          {/* Format */}
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Formato</h3>
            <p className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <span className="text-xl">
                {job.format === 'pdf' ? '📄' : job.format === 'csv' ? '📊' : '📈'}
              </span>
              {job.format.toUpperCase()}
            </p>
          </div>

          {/* Date Range */}
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Rango de Fechas</h3>
            <p className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <span>📅</span>
              {job.date_range}
            </p>
          </div>

          {/* User ID */}
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Usuario</h3>
            <p className="text-lg font-semibold text-gray-900 font-mono text-sm">{job.user_id}</p>
          </div>

          {/* Created At */}
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Fecha de Creación</h3>
            <p className="text-lg font-semibold text-gray-900">{formatDate(job.created_at)}</p>
          </div>

          {/* Updated At */}
          <div className="card">
            <h3 className="text-sm font-medium text-gray-500 mb-1">Última Actualización</h3>
            <p className="text-lg font-semibold text-gray-900">{formatDate(job.updated_at)}</p>
          </div>
        </div>

        {/* Result URL - only show if exists */}
        {job.result_url && (
          <div className="card mt-4">
            <h3 className="text-sm font-medium text-gray-500 mb-2">URL del Resultado</h3>
            <a
              href={job.result_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary-600 hover:text-primary-700 break-all text-sm font-mono"
            >
              {job.result_url}
            </a>
          </div>
        )}

        {/* Status Timeline */}
        <div className="card mt-4">
          <h3 className="text-sm font-medium text-gray-500 mb-4">Estado del Job</h3>
          <div className="flex items-center gap-2">
            <StatusIndicator 
              label="PENDING" 
              active={job.status === 'PENDING'} 
              icon="⏳"
            />
            <StatusConnector active={['PENDING', 'PROCESSING'].includes(job.status)} />
            <StatusIndicator 
              label="PROCESSING" 
              active={job.status === 'PROCESSING'} 
              icon="🔄"
            />
            <StatusConnector active={['PROCESSING', 'COMPLETED', 'FAILED'].includes(job.status)} />
            <StatusIndicator 
              label={job.status === 'FAILED' ? 'FAILED' : 'COMPLETED'} 
              active={job.status === 'COMPLETED' || job.status === 'FAILED'} 
              icon={job.status === 'FAILED' ? '❌' : '✅'}
            />
          </div>
        </div>

        {/* WebSocket Status */}
        <div className="mt-6 flex items-center justify-between text-sm text-gray-500">
          <span className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-300'}`}></span>
            {isConnected ? 'Conectado en tiempo real' : 'Sin conexión en tiempo real'}
          </span>
          <span>Actualizado: {formatShortDate(job.updated_at)}</span>
        </div>
      </div>
    </Layout>
  );
}

// Helper Components
function StatusIndicator({ label, active, icon }: { label: string; active: boolean; icon: string }) {
  return (
    <div className={`flex flex-col items-center ${active ? 'opacity-100' : 'opacity-40'}`}>
      <span className="text-2xl">{icon}</span>
      <span className={`text-xs font-medium mt-1 ${active ? 'text-gray-900' : 'text-gray-400'}`}>
        {label}
      </span>
    </div>
  );
}

function StatusConnector({ active }: { active: boolean }) {
  return (
    <div className={`flex-1 h-0.5 ${active ? 'bg-primary-500' : 'bg-gray-200'}`}></div>
  );
}