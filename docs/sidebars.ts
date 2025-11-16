import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  tutorialSidebar: [
    'Home',
    {
      type: 'category',
      label: 'Python SDK',
      items: [
        'Python/QuickStart',
        'Python/Client',
        'Python/Configuration',
      ],
    },
    {
      type: 'category',
      label: 'Platform',
      items: [
        'Platform/API Key page',
      ],
    },
    {
      type: 'doc',
      id: 'CHANGELOG',
      label: '📋 Changelog',
    },
  ],
};

export default sidebars;
