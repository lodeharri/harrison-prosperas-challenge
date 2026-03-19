---
name: frontend-component-design
description: Guidelines for building responsive components following SOLID and React 18 best practices.
---

# Instructions for Component Engineering

1. **SOLID Compliance**:
   - **Single Responsibility**: One component per file. Logic belongs to hooks.
   - **Interface Segregation**: Props must be typed strictly using TypeScript interfaces.
2. **Responsive Design**:
   - Use Tailwind's container classes.
   - Ensure interactive elements have minimum touch targets of 44px for mobile.
3. **React 18 Features**:
   - Use `useTransition` for non-urgent UI updates.
   - Implement `Suspense` boundaries for data-fetching components.
4. **Documentation**: Update `frontend/AGENTS.md` with the component dependency graph for every new feature.