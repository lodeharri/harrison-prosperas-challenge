import type { JobStatus } from '../../types';

interface JobBadgeProps {
  status: JobStatus;
}

export function JobBadge({ status }: JobBadgeProps) {
  const styles = {
    PENDING: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    PROCESSING: 'bg-blue-100 text-blue-800 border-blue-200',
    COMPLETED: 'bg-green-100 text-green-800 border-green-200',
    FAILED: 'bg-red-100 text-red-800 border-red-200',
  };

  const icons = {
    PENDING: '⏳',
    PROCESSING: '🔄',
    COMPLETED: '✅',
    FAILED: '❌',
  };

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${styles[status]}`}>
      <span>{icons[status]}</span>
      <span>{status}</span>
    </span>
  );
}
