export interface NavItem {
  name: string;
  href: string;
  iconName: string;
  badge?: string;
  requiredRole?: "viewer" | "analyst" | "admin";
}

export interface NavSection {
  title: string;
  items: NavItem[];
}

export const NAVIGATION_SECTIONS: NavSection[] = [
  {
    title: "Intelligence & Research",
    items: [
      {
        name: "Dashboard",
        href: "/",
        iconName: "LayoutDashboard",
      },
      {
        name: "Research & Search",
        href: "/search",
        iconName: "Search",
        badge: "Graph RAG",
      },
      {
        name: "Knowledge Graph",
        href: "/knowledge-graph",
        iconName: "Network",
      },
      {
        name: "Documents & Corpus",
        href: "/documents",
        iconName: "Files",
      },
    ],
  },
  {
    title: "Enterprise Browse",
    items: [
      {
        name: "Customers",
        href: "/browse/customers",
        iconName: "Users",
      },
      {
        name: "Incidents",
        href: "/browse/incidents",
        iconName: "AlertTriangle",
      },
      {
        name: "Decisions (ADRs)",
        href: "/browse/decisions",
        iconName: "FileCode",
      },
    ],
  },
];
