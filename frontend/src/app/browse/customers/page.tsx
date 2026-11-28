"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import {
  Users,
  Search,
  ArrowUpDown,
  Building2,
  DollarSign,
  Calendar,
  AlertCircle,
  Loader2,
  X,
  Sparkles,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import { apiClient } from "@/api/client";
import type { CustomerResponse } from "@/types/api";

const TIER_BADGES: Record<string, { bg: string; text: string; border: string }> = {
  enterprise: {
    bg: "bg-purple-950/60",
    text: "text-purple-300",
    border: "border-purple-800/60",
  },
  "mid-market": {
    bg: "bg-blue-950/60",
    text: "text-blue-300",
    border: "border-blue-800/60",
  },
  standard: {
    bg: "bg-emerald-950/60",
    text: "text-emerald-300",
    border: "border-emerald-800/60",
  },
  smb: {
    bg: "bg-gray-800/60",
    text: "text-gray-300",
    border: "border-gray-700/60",
  },
};

export default function CustomersBrowsePage() {
  const [customers, setCustomers] = useState<CustomerResponse[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<string>("");
  const [tierFilter, setTierFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"name" | "contract_value" | "tier">("contract_value");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerResponse | null>(null);

  const fetchCustomers = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.customers.list();
      setCustomers(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load customer records";
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  const filteredCustomers = useMemo(() => {
    return customers
      .filter((c) => {
        const matchesTier = tierFilter === "all" || c.tier === tierFilter;
        const q = search.toLowerCase();
        const matchesSearch =
          !q ||
          c.name.toLowerCase().includes(q) ||
          c.id.toLowerCase().includes(q) ||
          (c.industry && c.industry.toLowerCase().includes(q));
        return matchesTier && matchesSearch;
      })
      .sort((a, b) => {
        let cmp = 0;
        if (sortBy === "name") {
          cmp = a.name.localeCompare(b.name);
        } else if (sortBy === "contract_value") {
          cmp = a.contract_value - b.contract_value;
        } else if (sortBy === "tier") {
          cmp = a.tier.localeCompare(b.tier);
        }
        return sortOrder === "asc" ? cmp : -cmp;
      });
  }, [customers, search, tierFilter, sortBy, sortOrder]);

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
    }).format(val);
  };

  const toggleSort = (col: "name" | "contract_value" | "tier") => {
    if (sortBy === col) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortOrder("desc");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Customer Directory
          </h2>
          <p className="text-xs text-gray-400">
            Browse enterprise accounts, SLA tiers, contract values, and blast radius mappings.
          </p>
        </div>
        <button
          onClick={fetchCustomers}
          disabled={isLoading}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-gray-800 bg-gray-900 hover:bg-gray-800 text-xs text-gray-300 transition-colors w-fit"
        >
          <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search customers by name, ID, or industry..."
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-gray-900 border border-gray-800 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              <X size={14} />
            </button>
          )}
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-xs text-gray-400 font-mono">Tier:</span>
          <select
            data-testid="tier-filter-select"
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
            className="px-3 py-2 rounded-lg bg-gray-900 border border-gray-800 text-xs font-mono text-gray-200 focus:outline-none focus:border-blue-500 cursor-pointer"
          >
            <option value="all">All Tiers</option>
            <option value="enterprise">Enterprise</option>
            <option value="mid-market">Mid-Market</option>
            <option value="standard">Standard</option>
            <option value="smb">SMB</option>
          </select>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="flex items-center justify-between p-4 rounded-xl bg-red-950/40 border border-red-800 text-red-300 text-xs">
          <div className="flex items-center space-x-2">
            <AlertCircle size={16} className="flex-shrink-0" />
            <span>Failed to load customer records: {error}</span>
          </div>
          <button
            onClick={fetchCustomers}
            className="px-3 py-1 rounded bg-red-900/60 hover:bg-red-800 border border-red-700 text-xs font-medium"
          >
            Retry
          </button>
        </div>
      )}

      {/* Data Table */}
      <div className="rounded-xl border border-gray-800 bg-[#0d121f] overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/80 text-gray-400 font-mono text-[11px] uppercase tracking-wider">
                <th className="py-3 px-4">Customer ID</th>
                <th
                  onClick={() => toggleSort("name")}
                  className="py-3 px-4 cursor-pointer hover:text-gray-200 transition-colors"
                >
                  <div className="flex items-center space-x-1">
                    <span>Account Name</span>
                    <ArrowUpDown size={12} />
                  </div>
                </th>
                <th
                  onClick={() => toggleSort("tier")}
                  className="py-3 px-4 cursor-pointer hover:text-gray-200 transition-colors"
                >
                  <div className="flex items-center space-x-1">
                    <span>SLA Tier</span>
                    <ArrowUpDown size={12} />
                  </div>
                </th>
                <th
                  onClick={() => toggleSort("contract_value")}
                  className="py-3 px-4 cursor-pointer hover:text-gray-200 transition-colors"
                >
                  <div className="flex items-center space-x-1">
                    <span>Contract Value</span>
                    <ArrowUpDown size={12} />
                  </div>
                </th>
                <th className="py-3 px-4">Industry</th>
                <th className="py-3 px-4">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60 font-sans">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-gray-500">
                    <Loader2 size={24} className="animate-spin mx-auto mb-2 text-blue-500" />
                    <span>Loading customer records...</span>
                  </td>
                </tr>
              ) : filteredCustomers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-gray-500">
                    No customers match the active query.
                  </td>
                </tr>
              ) : (
                filteredCustomers.map((customer) => {
                  const badge = TIER_BADGES[customer.tier] || TIER_BADGES.smb;
                  const isSelected = selectedCustomer?.id === customer.id;

                  return (
                    <tr
                      key={customer.id}
                      data-testid={`customer-row-${customer.id}`}
                      onClick={() => setSelectedCustomer(customer)}
                      className={`hover:bg-gray-800/50 cursor-pointer transition-colors ${
                        isSelected ? "bg-blue-950/20" : ""
                      }`}
                    >
                      <td className="py-3 px-4 font-mono text-[11px] text-gray-400">
                        {customer.id}
                      </td>
                      <td className="py-3 px-4 font-medium text-gray-100 flex items-center space-x-2">
                        <Building2 size={14} className="text-gray-400 flex-shrink-0" />
                        <span>{customer.name}</span>
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase font-semibold border ${badge.bg} ${badge.text} ${badge.border}`}
                        >
                          {customer.tier}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono font-medium text-emerald-400">
                        {formatCurrency(customer.contract_value)}
                      </td>
                      <td className="py-3 px-4 text-gray-300">
                        {customer.industry || "—"}
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-gray-400">
                        {new Date(customer.created_at).toLocaleDateString("en-US", {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                        })}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Footer Count */}
        <div className="py-3 px-4 border-t border-gray-800 bg-gray-900/60 text-xs text-gray-400 flex items-center justify-between font-mono">
          <span>Showing {filteredCustomers.length} of {customers.length} accounts</span>
          <span className="text-gray-500 text-[11px]">Click a customer to inspect blast radius</span>
        </div>
      </div>

      {/* Customer Detail Drawer */}
      {selectedCustomer && (
        <div
          data-testid="customer-detail-drawer"
          className="rounded-xl border border-blue-500/30 bg-[#0e1628] p-5 shadow-2xl space-y-4 animate-in fade-in slide-in-from-top-2"
        >
          <div className="flex items-center justify-between border-b border-gray-800 pb-3">
            <div className="flex items-center space-x-2">
              <Building2 className="text-blue-400" size={18} />
              <h3 className="text-sm font-semibold text-white">
                Customer Profile — {selectedCustomer.name}
              </h3>
            </div>
            <button
              onClick={() => setSelectedCustomer(null)}
              className="p-1 rounded text-gray-400 hover:text-white hover:bg-gray-800"
            >
              <X size={16} />
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            <div className="space-y-1">
              <span className="text-[11px] text-gray-400 font-mono">Customer ID</span>
              <p className="font-mono text-gray-200">{selectedCustomer.id}</p>
            </div>
            <div className="space-y-1">
              <span className="text-[11px] text-gray-400 font-mono">SLA Tier</span>
              <p className="capitalize font-semibold text-gray-200">{selectedCustomer.tier}</p>
            </div>
            <div className="space-y-1">
              <span className="text-[11px] text-gray-400 font-mono">Annual Contract Value</span>
              <p className="font-mono font-bold text-emerald-400">
                {formatCurrency(selectedCustomer.contract_value)}
              </p>
            </div>
            <div className="space-y-1">
              <span className="text-[11px] text-gray-400 font-mono">Industry</span>
              <p className="text-gray-200">{selectedCustomer.industry || "General Enterprise"}</p>
            </div>
          </div>

          <div className="flex items-center justify-end space-x-3 pt-2">
            <Link
              href={`/search?q=${encodeURIComponent(
                `Which services and incidents impacted ${selectedCustomer.name}?`
              )}`}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors"
            >
              <Sparkles size={13} />
              <span>Analyze Incident Impact in Research</span>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
