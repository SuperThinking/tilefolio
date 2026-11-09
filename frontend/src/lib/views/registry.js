import Treemap from './Treemap.svelte';

// Visualization registry. Every view receives the same props: { rows, totals, settings, theme }.
// To add a view (e.g. sunburst, bar list, heat-grid): create views/<Name>.svelte and register it here;
// the Display tab lists every entry automatically.
export const VIEWS = {
  treemap: { label: 'Treemap', component: Treemap },
};

export const viewFor = (id) => (VIEWS[id] || VIEWS.treemap).component;
