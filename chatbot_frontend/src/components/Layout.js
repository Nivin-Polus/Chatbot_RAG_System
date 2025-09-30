import React from 'react';
import Sidebar from './Sidebar';

const Layout = ({
  sidebarProps,
  children,
  headerContent,
  className = ""
}) => {
  return (
    <div className={`min-h-screen bg-gray-50 ${className}`}>
      {/* Mobile Header */}
      <div className="lg:hidden bg-white shadow-sm border-b border-gray-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <button
              onClick={() => sidebarProps.onTabChange && sidebarProps.onTabChange(sidebarProps.activeTab)}
              className="p-2 text-gray-600 hover:text-gray-900"
            >
              <span className="text-xl">☰</span>
            </button>
            <h1 className="text-xl font-bold text-gray-900">{sidebarProps.title}</h1>
          </div>
          {headerContent && (
            <div className="flex items-center space-x-2">
              {headerContent}
            </div>
          )}
        </div>
      </div>

      <div className="flex h-screen">
        {/* Sidebar */}
        <Sidebar {...sidebarProps} />

        {/* Main Content Area */}
        <div className="flex-1 lg:ml-0 flex flex-col overflow-hidden">
          {/* Desktop Header */}
          <div className="hidden lg:block bg-white shadow-sm border-b border-gray-200 px-6 py-4 flex-shrink-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="w-10" />
                <div className="flex items-center space-x-2 text-sm text-gray-600">
                  <span>{sidebarProps.title}</span>
                  <span>/</span>
                  <span className="font-medium text-gray-900">
                    {sidebarProps.menuItems.find(item => item.id === sidebarProps.activeTab)?.label || 'Dashboard'}
                  </span>
                </div>
              </div>
              
              {headerContent && (
                <div className="flex items-center space-x-2">
                  {headerContent}
                </div>
              )}
            </div>
          </div>
          
          {/* Scrollable Content Area */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-6">
              {children}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Layout;
