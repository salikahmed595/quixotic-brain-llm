import type { ComponentType } from 'react';
import { AddPage, ApprovalsPage, KnowledgePage } from './Knowledge';
import { DocumentsPage, SalesPage } from './Files';
import { DepartmentsPage, RequestsPage, UsersPage } from './People';
import { DashboardPage, InsightsPage, KeysPage, SystemPage, VocabularyPage } from './Ops';

/* Admin pages open in the main panel without changing the sidebar (PRD §4.3). Keys match the sidebar ids. */
export const PAGES: Record<string, ComponentType> = {
  knowledge: KnowledgePage, add: AddPage, documents: DocumentsPage, sales: SalesPage,
  approvals: ApprovalsPage, requests: RequestsPage, dashboard: DashboardPage, insights: InsightsPage,
  users: UsersPage, departments: DepartmentsPage, vocabulary: VocabularyPage, keys: KeysPage, system: SystemPage,
};
