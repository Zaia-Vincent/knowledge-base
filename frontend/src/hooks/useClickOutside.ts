import { useEffect } from 'react';

/**
 * Calls `handler` when a click or touch occurs outside the element
 * referenced by `ref`. Useful for dismissing dropdowns, popovers, etc.
 */
export function useClickOutside(
    ref: React.RefObject<HTMLElement | null>,
    handler: () => void,
): void {
    useEffect(() => {
        function handleEvent(event: MouseEvent | TouchEvent) {
            if (!ref.current || ref.current.contains(event.target as Node)) {
                return;
            }
            handler();
        }

        document.addEventListener('mousedown', handleEvent);
        document.addEventListener('touchstart', handleEvent);

        return () => {
            document.removeEventListener('mousedown', handleEvent);
            document.removeEventListener('touchstart', handleEvent);
        };
    }, [ref, handler]);
}
