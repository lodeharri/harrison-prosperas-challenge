interface HeaderProps {
  userId: string | null;
  onLogout: () => void;
  wsConnected: boolean;
}

export function Header({ userId, onLogout, wsConnected }: HeaderProps) {
  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">RP</span>
            </div>
            <h1 className="text-xl font-bold text-gray-900">Reto Prosperas</h1>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm">
              <span className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-gray-400'}`}></span>
              <span className="text-gray-600">{wsConnected ? 'Conectado' : 'Desconectado'}</span>
            </div>
            
            {userId && (
              <div className="flex items-center gap-3">
                <span className="text-sm text-gray-600">Usuario: <strong>{userId}</strong></span>
                <button
                  onClick={onLogout}
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  Cerrar sesión
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
