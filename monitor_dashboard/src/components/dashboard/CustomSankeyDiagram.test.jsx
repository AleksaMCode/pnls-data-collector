// Unit tests of the device → manufacturer → country Sankey diagram.
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import CustomSankeyDiagram from './CustomSankeyDiagram';

/** The tooltips of the diagram's links and nodes. */
function titles(container) {
  return [...container.querySelectorAll('title')].map((t) => t.textContent);
}

describe('CustomSankeyDiagram', () => {
  it('says so when there is no data', () => {
    const { rerender } = render(<CustomSankeyDiagram sankeyData={{}} />);
    expect(screen.getByText('No Sankey data available.')).toBeInTheDocument();

    rerender(<CustomSankeyDiagram sankeyData={null} />);
    expect(screen.getByText('No Sankey data available.')).toBeInTheDocument();

    // A device without manufacturers has no links to draw.
    rerender(<CustomSankeyDiagram sankeyData={{ 'RPI-1': {} }} />);
    expect(screen.getByText('No Sankey data available.')).toBeInTheDocument();
  });

  it('links each device to its manufacturers and each manufacturer to its country', () => {
    const { container } = render(
      <CustomSankeyDiagram
        sankeyData={{
          'rpi-1': {
            'Apple, Inc.': { country: 'United States' },
            Samsung: { country: 'South Korea' },
          },
          'RPI-2': {
            'Apple, Inc.': { country: 'United States' },
            Acme: { country: null },
          },
        }}
      />,
    );

    expect(
      screen.getByRole('img', {
        name: 'Sankey diagram of device, company, and country',
      }),
    ).toBeInTheDocument();
    expect(titles(container)).toEqual(
      expect.arrayContaining([
        // Device labels are upper-cased.
        'RPI-1 -> Apple, Inc.: 1',
        'RPI-1 -> Samsung: 1',
        'RPI-2 -> Apple, Inc.: 1',
        'RPI-2 -> Acme: 1',
        // A manufacturer seen by two devices is one node with both links.
        'Apple, Inc. -> UNITED STATES: 2',
        'Samsung -> SOUTH KOREA: 1',
        // A manufacturer without a country goes to "UNK".
        'Acme -> UNK: 1',
        'RPI-1 (2)',
        'Apple, Inc. (2)',
        'UNITED STATES (2)',
        'UNK (1)',
      ]),
    );
  });

  it('skips manufacturers without a name', () => {
    const { container } = render(
      <CustomSankeyDiagram
        sankeyData={{ 'RPI-1': { '': { country: 'X' }, Acme: {} } }}
      />,
    );

    expect(titles(container).filter((t) => t.includes('->'))).toEqual([
      'RPI-1 -> Acme: 1',
      'Acme -> UNK: 1',
    ]);
  });

  it('orders manufacturers by how many devices see them', () => {
    const { container } = render(
      <CustomSankeyDiagram
        sankeyData={{
          'RPI-1': { Rare: {}, Common: {} },
          'RPI-2': { Common: {} },
        }}
      />,
    );

    const companyLabels = [...container.querySelectorAll('text')]
      .map((t) => t.textContent)
      .filter((label) => label === 'Rare' || label === 'Common');
    expect(companyLabels).toEqual(['Common', 'Rare']);
  });

  it.fails(
    'draws a manufacturer whose name contains "->". Known bug: the name is split as if it were a link key',
    () => {
      render(
        <CustomSankeyDiagram
          sankeyData={{ 'RPI-1': { 'A->B Corp': { country: 'France' } } }}
        />,
      );

      expect(screen.getByText('A->B Corp')).toBeInTheDocument();
    },
  );
});
