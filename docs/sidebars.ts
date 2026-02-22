import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  tutorialSidebar: [
    'Home',
    'getting-started',
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
    'api-reference',
    'sdks',
    {
      type: 'link',
      label: '📋 Changelog',
      href: 'https://github.com/SelfMemory/SelfMemory/blob/master/CHANGELOG.md',
    },
  ],
};

export default sidebars;
