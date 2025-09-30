import React from 'react';

const Sidebar = ({ 
  isOpen, 
  onClose, 
  title, 
  icon, 
  menuItems, 
  activeTab, 
  onTabChange, 
  userInfo, 
  onLogout,
  className = ""
}) => {
  return (
    <div className={`fixed inset-y-0 left-0 z-50 w-64 h-screen bg-gradient-to-b from-primary-600 to-primary-700 transform transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:inset-0 ${className} ${
      isOpen ? 'translate-x-0' : '-translate-x-full'
    }`}>
      {/* Header */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-primary-500">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center">
            <span className="text-white text-lg">{icon}</span>
          </div>
          <span className="text-white font-bold text-lg">{title}</span>
        </div>
        <button
          onClick={onClose}
          className="lg:hidden p-2 text-white/80 hover:text-white"
        >
          <span className="text-xl">✕</span>
        </button>
      </div>

      {/* Navigation */}
      <nav className="mt-6 px-4 flex-1 overflow-y-auto">
        <div className="space-y-2">
          {menuItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`w-full flex items-center space-x-3 px-4 py-3 text-left rounded-lg transition-all duration-200 ${
                  activeTab === item.id
                    ? 'bg-white/20 text-white font-semibold'
                    : 'text-white/80 hover:bg-white/10 hover:text-white'
                }`}
              >
                {typeof Icon === 'function' ? <Icon /> : <span className="text-xl">{Icon}</span>}
                <div>
                  <div className="font-medium">{item.label}</div>
                  <div className="text-xs opacity-75">{item.description}</div>
                </div>
              </button>
            );
          })}
        </div>
      </nav>

      {/* User Info */}
      <div className="p-4 border-t border-primary-500">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center">
            <span className="text-white text-sm">👤</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-white font-medium truncate">{userInfo.name}</div>
            <div className="text-white/80 text-sm truncate">{userInfo.role}</div>
          </div>
          {onLogout && (
            <button
              onClick={onLogout}
              className="p-2 text-white/80 hover:text-white transition-colors"
              title="Logout"
            >
              <span className="text-xl">🚪</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
