import { useState, useMemo } from 'react';
import { JobCard } from './JobCard';
import { getReportTypeLabel } from '../../reportTypes';
import type { Job } from '../../types';

/**
 * Spanish-to-English mapping for report type search
 * Allows users to search in Spanish and find English report_type values
 */
const SPANISH_TO_ENGLISH_MAP: Record<string, string[]> = {
  // Spanish search terms that should match sales_report
  'ventas': ['sales_report'],
  'venta': ['sales_report'],
  'vender': ['sales_report'],
  
  // Spanish search terms that should match financial_report
  'financiero': ['financial_report'],
  'financiera': ['financial_report'],
  'finanzas': ['financial_report'],
  
  // Spanish search terms that should match inventory_report
  'inventario': ['inventory_report'],
  'stock': ['inventory_report'],
  'almacén': ['inventory_report'],
  
  // Spanish search terms that should match customer_report
  'clientes': ['customer_report'],
  'cliente': ['customer_report'],
  'consumidor': ['customer_report'],
  
  // Spanish search terms that should match custom_report
  'personalizado': ['custom_report'],
  'personalizada': ['custom_report'],
  'custom': ['custom_report'],
};

/**
 * Check if a Spanish search term matches a report type
 * @param spanishTerm - The Spanish search term
 * @param reportType - The English report type to check
 * @returns true if the Spanish term matches the report type
 */
function spanishTermMatchesReportType(spanishTerm: string, reportType: string): boolean {
  const normalizedTerm = spanishTerm.toLowerCase().trim();
  const englishMatches = SPANISH_TO_ENGLISH_MAP[normalizedTerm];
  
  if (englishMatches) {
    return englishMatches.includes(reportType);
  }
  
  // Also check if the Spanish term appears in the Spanish label
  const spanishLabel = getReportTypeLabel(reportType).toLowerCase();
  return spanishLabel.includes(normalizedTerm);
}

interface JobListProps {
  jobs: Job[];
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (newPage: number) => void;
}

export function JobList({ jobs, isLoading, error, onRefresh, page, pageSize, total, onPageChange }: JobListProps) {
  const [searchTerm, setSearchTerm] = useState('');
  
  const totalPages = Math.ceil(total / pageSize);
  const isFirstPage = page <= 1;
  const isLastPage = page >= totalPages;
  
  // Calculate showing range
  const showingFrom = total > 0 ? (page - 1) * pageSize + 1 : 0;
  const showingTo = Math.min(page * pageSize, total);
  
  // Filter jobs by report_type only with Spanish-to-English search support
  const filteredJobs = useMemo(() => {
    if (!searchTerm.trim()) return jobs;
    const term = searchTerm.toLowerCase().trim();
    
    return jobs.filter(job => {
      // First check direct English match
      if (job.report_type?.toLowerCase().trim().includes(term)) {
        return true;
      }
      
      // Check Spanish-to-English mapping
      if (spanishTermMatchesReportType(term, job.report_type)) {
        return true;
      }
      
      // Check if term appears in Spanish label
      const spanishLabel = getReportTypeLabel(job.report_type).toLowerCase();
      if (spanishLabel.includes(term)) {
        return true;
      }
      
      return false;
    });
  }, [jobs, searchTerm]);
  
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Mis Reportes</h2>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50"
        >
          <svg className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Actualizar
        </button>
      </div>

      {/* Search Filter */}
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        <input
          type="text"
          placeholder="Buscar por tipo de reporte (ej: ventas, financiero, inventario)..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg leading-5 bg-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
        />
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Top Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600">
              Mostrando <span className="font-medium text-gray-900">{showingFrom}-{showingTo}</span> de <span className="font-medium text-gray-900">{total}</span> trabajos
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-900 bg-white px-3 py-1.5 rounded-md border border-gray-300">
              Página {page} de {totalPages}
            </span>
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={isFirstPage || isLoading}
              className="px-3 py-1.5 text-sm rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Anterior
            </button>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={isLastPage || isLoading}
              className="px-3 py-1.5 text-sm rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Siguiente
            </button>
          </div>
        </div>
      )}

      {isLoading && filteredJobs.length === 0 ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <svg className="mx-auto h-12 w-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          {searchTerm ? (
            <p>No hay trabajos que coincidan con "{searchTerm}"</p>
          ) : (
            <>
              <p>No tienes reportes solicitados</p>
              <p className="text-sm">Solicita tu primer reporte usando el formulario</p>
            </>
          )}
        </div>
      ) : (
        <div className="overflow-y-auto h-[calc(100vh-300px)] border border-gray-200 rounded-lg">
          <div className="space-y-3 p-3">
            {filteredJobs.map((job) => (
              <JobCard key={job.job_id} job={job} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
