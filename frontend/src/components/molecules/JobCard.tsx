import React from 'react';
import { Badge, Button } from '../atoms';

export interface JobCardData {
  id: number;
  job_title: string;
  company: string;
  location?: string | null;
  job_type?: string | null;
  status: string;
  has_easy_apply: boolean;
  applied_at?: string | null;
}

export interface JobCardProps {
  job: JobCardData;
  onApply?: (job: JobCardData) => void;
}

const statusColor: Record<string, 'green' | 'blue' | 'yellow' | 'gray' | 'red'> = {
  applied: 'green',
  found: 'blue',
  interview: 'green',
  offer: 'green',
  rejected: 'red',
  skipped: 'gray',
  skipped_incomplete_form: 'yellow',
  skipped_no_easy_apply: 'gray',
};

export const JobCard: React.FC<JobCardProps> = ({ job, onApply }) => {
  const color = statusColor[job.status] ?? 'gray';

  return (
    <div className="flex items-start justify-between rounded-xl border border-gray-200 bg-white p-4 shadow-sm gap-4">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <h3 className="text-sm font-semibold text-gray-800 truncate">{job.job_title}</h3>
          <Badge label={job.status.replace(/_/g, ' ')} color={color} />
          {job.has_easy_apply && (
            <Badge label="Easy Apply" color="blue" />
          )}
        </div>

        <p className="text-sm text-gray-600">{job.company}</p>

        <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
          {job.location && <span>{job.location}</span>}
          {job.job_type && <span>{job.job_type}</span>}
          {job.applied_at && (
            <span>
              Applied: {new Date(job.applied_at).toLocaleDateString('id-ID')}
            </span>
          )}
        </div>
      </div>

      {onApply && job.status === 'found' && job.has_easy_apply && (
        <Button
          variant="primary"
          size="sm"
          onClick={() => onApply(job)}
          aria-label={`Lamar ${job.job_title}`}
        >
          Lamar
        </Button>
      )}
    </div>
  );
};
