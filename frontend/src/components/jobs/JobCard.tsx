import { Link } from 'react-router-dom';
import { JobBadge } from './JobBadge';
import { getReportTypeLabel } from '../../reportTypes';
import type { Job } from '../../types';

interface JobCardProps {
  job: Job;
}

export function JobCard({ job }: JobCardProps) {
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 hover:shadow-md transition-shadow group">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <Link 
            to={`/jobs/${job.job_id}`}
            className="flex items-center gap-2 mb-2 hover:underline decoration-2 decoration-primary-500/30"
          >
            <h3 className="font-semibold text-gray-900 truncate group-hover:text-primary-600">
              {getReportTypeLabel(job.report_type)}
            </h3>
            <JobBadge status={job.status} />
          </Link>
          
          <div className="space-y-1 text-sm text-gray-600">
            <div className="flex items-center gap-2">
              <span className="font-medium">ID:</span>
              <Link 
                to={`/jobs/${job.job_id}`} 
                className="font-mono text-xs text-primary-600 hover:text-primary-700 hover:underline"
              >
                {job.job_id.slice(0, 8)}...
              </Link>
            </div>
            <div className="flex items-center gap-4">
              <span>📅 {job.date_range}</span>
              <span>📄 {job.format.toUpperCase()}</span>
            </div>
            <div className="text-xs text-gray-500">
              Creado: {formatDate(job.created_at)}
            </div>
          </div>
        </div>

        {job.result_url && job.status === 'COMPLETED' && (
          <a
            href={job.result_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-shrink-0 btn-primary text-sm"
          >
            Descargar
          </a>
        )}
      </div>
      
      {/* View Details Link - Desktop */}
      <div className="mt-3 pt-3 border-t border-gray-100">
        <Link 
          to={`/jobs/${job.job_id}`}
          className="text-sm text-primary-600 hover:text-primary-700 font-medium inline-flex items-center gap-1"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          Ver detalles
        </Link>
      </div>
    </div>
  );
}
