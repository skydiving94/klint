import React, {
  useState,
  useEffect,
  useCallback,
} from 'react';
import _ from 'lodash';
import * as moment from 'moment';

interface Product {
  id: string;
  name: string;
  price: number;
}

export function ProductSearchList({
  products,
}: {
  products: Product[];
}) {
  const [query, setQuery] = useState('');
  const [filteredProducts, setFilteredProducts] = useState<
    Product[]
  >([]);
  const [lastUpdated, setLastUpdated] = useState('');

  useEffect(() => {
    const matches = _.filter(products, (p) =>
      p.name.toLowerCase().includes(query.toLowerCase()),
    );
    setFilteredProducts(matches);
    setLastUpdated(moment.now().toString());
  });

  const logSearchAnalytics = useCallback(() => {
    console.log('Searched query:', query);
  }, []);

  const handleHighlightInput = () => {
    const inputElement = document.getElementById(
      'product-search-input',
    );
    if (inputElement) {
      inputElement.style.border = '2px solid red';
      inputElement.focus();
    }
  };

  return (
    <div>
      <input
        id='product-search-input'
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          logSearchAnalytics();
        }}
      />
      <button onClick={() => handleHighlightInput()}>
        Highlight Search
      </button>
      <p>Last updated: {lastUpdated}</p>
      <ul>
        {filteredProducts.map((item) => (
          <li
            key={item.id}
            onClick={() => {
              const row = document.getElementById(
                `row-${item.id}`,
              );
              if (row) row.style.backgroundColor = 'yellow';
            }}
            id={`row-${item.id}`}
          >
            {item.name} - ${item.price}
          </li>
        ))}
      </ul>
    </div>
  );
}
