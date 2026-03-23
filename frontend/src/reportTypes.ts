/**
 * Utility functions for report type translations
 */

/**
 * Maps English report_type values to Spanish labels
 */
export const REPORT_TYPE_LABELS: Record<string, string> = {
  sales_report: 'Reporte de Ventas',
  financial_report: 'Reporte Financiero',
  inventory_report: 'Reporte de Inventario',
  customer_report: 'Reporte de Clientes',
  custom_report: 'Reporte Personalizado',
};

/**
 * Get Spanish label for a report type
 * @param reportType - The English report type key (e.g., 'sales_report')
 * @returns Spanish label or the original value if not found
 */
export function getReportTypeLabel(reportType: string): string {
  return REPORT_TYPE_LABELS[reportType] || reportType;
}