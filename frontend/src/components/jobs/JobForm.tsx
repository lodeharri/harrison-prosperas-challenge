import { useState } from 'react';

interface JobFormProps {
  onSubmit: (data: { report_type: string; date_range: string; format: string }) => Promise<boolean>;
  isLoading?: boolean;
}

export function JobForm({ onSubmit, isLoading }: JobFormProps) {
  const [reportType, setReportType] = useState('');
  const [dateRange, setDateRange] = useState('all');
  const [format, setFormat] = useState('pdf');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit({
      report_type: reportType,
      date_range: dateRange,
      format,
    });
    setReportType('');
    setDateRange('all');
    setFormat('pdf');
  };

  return (
    <form onSubmit={handleSubmit} className="card space-y-4">
      <h2 className="text-lg font-semibold text-gray-900">Solicitar Nuevo Reporte</h2>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Tipo de Reporte *
        </label>
        <select
          value={reportType}
          onChange={(e) => setReportType(e.target.value)}
          required
          className="input-field"
        >
          <option value="">Seleccionar tipo...</option>
          <option value="sales_report">Reporte de Ventas</option>
          <option value="financial_report">Reporte Financiero</option>
          <option value="inventory_report">Reporte de Inventario</option>
          <option value="customer_report">Reporte de Clientes</option>
          <option value="custom_report">Reporte Personalizado</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Rango de Fechas
        </label>
        <select
          value={dateRange}
          onChange={(e) => setDateRange(e.target.value)}
          className="input-field"
        >
          <option value="all">Todo el período</option>
          <option value="today">Hoy</option>
          <option value="week">Esta semana</option>
          <option value="month">Este mes</option>
          <option value="quarter">Este trimestre</option>
          <option value="year">Este año</option>
          <option value="custom">Personalizado</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Formato de Salida
        </label>
        <div className="flex gap-4">
          {['pdf', 'csv', 'excel'].map((f) => (
            <label key={f} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="format"
                value={f}
                checked={format === f}
                onChange={(e) => setFormat(e.target.value)}
                className="text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm text-gray-700 uppercase">{f}</span>
            </label>
          ))}
        </div>
      </div>

      <button
        type="submit"
        disabled={isLoading || !reportType}
        className="btn-primary w-full"
      >
        {isLoading ? 'Enviando...' : 'Solicitar Reporte'}
      </button>
    </form>
  );
}
