import { JobBadge } from './JobBadge';
import type { Job } from '../../types';

interface JobCardProps {
  job: Job;
}

export function JobCard({ job }: JobCardProps) {
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <h3 className="font-semibold text-gray-900 truncate">{job.report_type}</h3>
            <JobBadge status={job.status} />
          </div>
          
          <div className="space-y-1 text-sm text-gray-600">
            <div className="flex items-center gap-2">
              <span className="font-medium">ID:</span>
              <span className="font-mono text-xs">{job.job_id.slice(0, 8)}...</span>
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
    </div>
  );
}
