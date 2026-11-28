import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import CustomersBrowsePage from "../page";
import { apiClient } from "@/api/client";
import type { CustomerResponse } from "@/types/api";

describe("CustomersBrowsePage Component", () => {
  const mockCustomers: CustomerResponse[] = [
    {
      id: "cust-acme",
      name: "Acme Corp",
      tier: "enterprise",
      contract_value: 2400000.0,
      industry: "FinTech",
      created_at: "2026-01-15T08:00:00Z",
    },
    {
      id: "cust-techflow",
      name: "TechFlow Systems",
      tier: "mid-market",
      contract_value: 750000.0,
      industry: "Logistics",
      created_at: "2026-02-10T10:30:00Z",
    },
    {
      id: "cust-smb-01",
      name: "Acme Retail SMB",
      tier: "smb",
      contract_value: 50000.0,
      industry: "Retail",
      created_at: "2026-03-01T12:00:00Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders page title and table columns", async () => {
    vi.spyOn(apiClient.customers, "list").mockResolvedValue(mockCustomers);

    render(<CustomersBrowsePage />);

    expect(screen.getByText("Customer Directory")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });

    expect(screen.getByText("Customer ID")).toBeInTheDocument();
    expect(screen.getByText("Account Name")).toBeInTheDocument();
    expect(screen.getByText("SLA Tier")).toBeInTheDocument();
    expect(screen.getByText("Contract Value")).toBeInTheDocument();
    expect(screen.getByText("Industry")).toBeInTheDocument();
  });

  it("displays formatted currency values and tier badges", async () => {
    vi.spyOn(apiClient.customers, "list").mockResolvedValue(mockCustomers);

    render(<CustomersBrowsePage />);

    await waitFor(() => {
      expect(screen.getByText("$2,400,000.00")).toBeInTheDocument();
    });

    expect(screen.getByText("$750,000.00")).toBeInTheDocument();
    expect(screen.getAllByText("enterprise").length).toBeGreaterThan(0);
    expect(screen.getAllByText("mid-market").length).toBeGreaterThan(0);
  });

  it("filters customer records by search input", async () => {
    vi.spyOn(apiClient.customers, "list").mockResolvedValue(mockCustomers);

    render(<CustomersBrowsePage />);

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search customers/i);
    fireEvent.change(searchInput, { target: { value: "TechFlow" } });

    expect(screen.getByText("TechFlow Systems")).toBeInTheDocument();
    expect(screen.queryByText("Acme Corp")).not.toBeInTheDocument();
  });

  it("filters customer records by SLA tier selector", async () => {
    vi.spyOn(apiClient.customers, "list").mockResolvedValue(mockCustomers);

    render(<CustomersBrowsePage />);

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });

    const tierSelect = screen.getByTestId("tier-filter-select");
    fireEvent.change(tierSelect, { target: { value: "enterprise" } });

    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.queryByText("TechFlow Systems")).not.toBeInTheDocument();
    expect(screen.queryByText("Acme Retail SMB")).not.toBeInTheDocument();
  });

  it("opens customer detail drawer when row is clicked", async () => {
    vi.spyOn(apiClient.customers, "list").mockResolvedValue(mockCustomers);

    render(<CustomersBrowsePage />);

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });

    const customerRow = screen.getByTestId("customer-row-cust-acme");
    fireEvent.click(customerRow);

    const drawer = screen.getByTestId("customer-detail-drawer");
    expect(drawer).toBeInTheDocument();
    expect(drawer).toHaveTextContent(/Customer Profile/);
    expect(drawer).toHaveTextContent("cust-acme");
  });

  it("renders error alert with retry button on fetch failure", async () => {
    vi.spyOn(apiClient.customers, "list").mockRejectedValue(new Error("Network Error"));

    render(<CustomersBrowsePage />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load customer records/i)).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });
});
