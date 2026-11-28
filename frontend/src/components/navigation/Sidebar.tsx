"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Search,
  Network,
  Files,
  Users,
  AlertTriangle,
  FileCode,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { NAVIGATION_SECTIONS, NavItem } from "./NavLinks";

const ICON_MAP: Record<string, React.ElementType> = {
  LayoutDashboard,
  Search,
  Network,
  Files,
  Users,
  AlertTriangle,
  FileCode,
};

export interface SidebarProps {
  currentRole?: "viewer" | "analyst" | "admin";
}

export function Sidebar({ currentRole = "analyst" }: SidebarProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      data-testid="app-sidebar"
      className={`relative flex flex-col border-r border-gray-800 bg-[#0d121f] transition-all duration-300 ease-in-out ${
        collapsed ? "w-20" : "w-64"
      } min-h-screen z-30 select-none`}
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-gray-800 bg-[#0e1526]">
        {!collapsed && (
          <Link href="/" className="flex items-center space-x-2.5 overflow-hidden">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-600 shadow-lg shadow-blue-500/20 text-white font-bold text-base">
              N
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-sm tracking-wide text-white">
                NovaEnterprise
              </span>
              <span className="text-[10px] text-gray-400 font-mono tracking-tighter uppercase">
                Intelligence Console
              </span>
            </div>
          </Link>
        )}
        {collapsed && (
          <div className="mx-auto flex items-center justify-center w-8 h-8 rounded-lg bg-blue-600 text-white font-bold text-base">
            N
          </div>
        )}

        <button
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="p-1.5 rounded-md text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      {/* Navigation Groups */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        {NAVIGATION_SECTIONS.map((section) => (
          <div key={section.title} className="space-y-1">
            {!collapsed && (
              <h3 className="px-3 text-[11px] font-semibold text-gray-400 tracking-wider uppercase font-mono mb-2">
                {section.title}
              </h3>
            )}
            <nav className="space-y-1">
              {section.items.map((item: NavItem) => {
                const IconComponent = ICON_MAP[item.iconName] || Search;
                const isActive =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={collapsed ? item.name : undefined}
                    className={`flex items-center group px-3 py-2 text-xs font-medium rounded-lg transition-colors ${
                      isActive
                        ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                        : "text-gray-400 hover:text-gray-100 hover:bg-gray-800/60"
                    }`}
                  >
                    <IconComponent
                      size={18}
                      className={`flex-shrink-0 ${
                        isActive
                          ? "text-blue-400"
                          : "text-gray-400 group-hover:text-gray-200"
                      }`}
                    />
                    {!collapsed && (
                      <span className="ml-3 truncate">{item.name}</span>
                    )}
                    {!collapsed && item.badge && (
                      <span className="ml-auto px-1.5 py-0.5 text-[9px] font-mono font-medium rounded bg-blue-900/60 text-blue-300 border border-blue-700/40">
                        {item.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </nav>
          </div>
        ))}
      </div>

      {/* Footer Role / Mode Status */}
      <div className="p-3 border-t border-gray-800 bg-[#090d16]">
        <div className="flex items-center space-x-3 px-2 py-1.5 rounded-lg bg-gray-900/80 border border-gray-800">
          <ShieldCheck size={18} className="text-emerald-400 flex-shrink-0" />
          {!collapsed && (
            <div className="flex flex-col min-w-0">
              <span className="text-[11px] font-medium text-gray-200 truncate">
                Role: <span className="font-mono text-emerald-400 font-semibold">{currentRole}</span>
              </span>
              <span className="text-[9px] text-gray-400 font-mono">
                Port :3001 ↔ :8001
              </span>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
