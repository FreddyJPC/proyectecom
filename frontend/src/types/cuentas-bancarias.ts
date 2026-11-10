/** Una cuenta del dueño a la que Victoria le pide al cliente que transfiera (`/cuentas-bancarias`). */
export type CuentaBancaria = {
  id: number;
  banco: string;
  tipoCuenta: string;
  numero: string;
  titular: string;
  /** Cédula o RUC del titular; se le muestra al cliente. */
  identificacion: string | null;
  activa: boolean;
  /** La de menor orden es la principal. */
  orden: number;
};
