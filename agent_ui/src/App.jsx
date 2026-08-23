import { useMemo, useState } from 'react'
import './App.css'

const products = [
  {
    id: 1,
    name: 'PlayStation 5',
    brand: 'Sony',
    price: 54999,
    description: 'Ultra-fast SSD performance with cinematic visuals for immersive gameplay.',
    badge: 'Best Seller',
    accent: 'bg-[#efe1d5]',
    image:
      'https://images.unsplash.com/photo-1606813907291-d86efa9b94db?auto=format&fit=crop&w=900&q=80',
  },
  {
    id: 2,
    name: 'Xbox Series X',
    brand: 'Microsoft',
    price: 49999,
    description: 'High-fidelity gaming with seamless compatibility and premium speed.',
    badge: 'New Arrival',
    accent: 'bg-[#e7d9c8]',
    image:
      'https://images.unsplash.com/photo-1621259182978-f8f2c1d92c7a?auto=format&fit=crop&w=900&q=80',
  },
  {
    id: 3,
    name: 'Nintendo Switch OLED',
    brand: 'Nintendo',
    price: 31999,
    description: 'Portable flexibility and vibrant visuals for casual and competitive play.',
    badge: 'Popular',
    accent: 'bg-[#f1e6dc]',
    image:
      'https://images.unsplash.com/photo-1578303512597-81e6cc155b3e?auto=format&fit=crop&w=900&q=80',
  },
  {
    id: 4,
    name: 'PS5 Digital Edition',
    brand: 'Sony',
    price: 44999,
    description: 'A streamlined digital-first console built for modern game libraries.',
    badge: 'Limited',
    accent: 'bg-[#eadbc6]',
    image:
      'https://images.unsplash.com/photo-1606144042614-b2417e99c4e3?auto=format&fit=crop&w=900&q=80',
  },
  {
    id: 5,
    name: '4K Gaming Monitor',
    brand: 'Acer',
    price: 18999,
    description: 'Smooth visuals and sharp detail for competitive and cinematic gaming.',
    badge: 'Value Pick',
    accent: 'bg-[#f3e6d8]',
    image:
      'https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=900&q=80',
  },
  {
    id: 6,
    name: 'RGB Mechanical Keyboard',
    brand: 'Redragon',
    price: 5999,
    description: 'Responsive key switches and tactile feedback for intense gaming sessions.',
    badge: 'Hot Deal',
    accent: 'bg-[#eadcc5]',
    image:
      'https://images.unsplash.com/photo-1511467687858-23d96c32e4ae?auto=format&fit=crop&w=900&q=80',
  },
  {
    id: 7,
    name: 'Gaming Mouse',
    brand: 'Logitech',
    price: 3999,
    description: 'Precision control and ergonomic comfort for fast-paced gameplay.',
    badge: 'Top Rated',
    accent: 'bg-[#f0e3d7]',
    image:
      'https://images.unsplash.com/photo-1563294328-23b5acefa4f8?auto=format&fit=crop&w=900&q=80',
  },
  {
    id: 8,
    name: 'Wireless Noise Cancelling Headphones',
    brand: 'Sony',
    price: 12999,
    description: 'Deep immersion with comfort-first design for long gaming and work sessions.',
    badge: 'Popular',
    accent: 'bg-[#ecdfd3]',
    image:
      'https://images.unsplash.com/photo-1546435770-a3e426bf472b?auto=format&fit=crop&w=900&q=80',
  },
  {
    id: 9,
    name: 'AirPods Pro',
    brand: 'Apple',
    price: 19999,
    description: 'Wireless audio with adaptive noise control for calls, music, and gaming.',
    badge: 'Premium',
    accent: 'bg-[#f5e7d7]',
    image:
      'https://images.unsplash.com/photo-1606220588913-b3aacb4d2f46?auto=format&fit=crop&w=900&q=80',
  },
  {
    id: 10,
    name: 'USB-C Hub + Dock',
    brand: 'Anker',
    price: 4999,
    description: 'Expand productivity with multi-port connectivity for desktop setups.',
    badge: 'Desk Essential',
    accent: 'bg-[#e9d8c8]',
    image:
      'https://images.unsplash.com/photo-1585771724684-38269d6639fd?auto=format&fit=crop&w=900&q=80',
  },
]

function App() {
  const [cart, setCart] = useState([])
  const [showCheckout, setShowCheckout] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    address: '',
  })

  const addToCart = (product) => {
    setCart((currentCart) => {
      const existing = currentCart.find((item) => item.id === product.id)

      if (existing) {
        return currentCart.map((item) =>
          item.id === product.id ? { ...item, quantity: item.quantity + 1 } : item,
        )
      }

      return [...currentCart, { ...product, quantity: 1 }]
    })
  }

  const updateQuantity = (productId, change) => {
    setCart((currentCart) =>
      currentCart
        .map((item) =>
          item.id === productId ? { ...item, quantity: Math.max(0, item.quantity + change) } : item,
        )
        .filter((item) => item.quantity > 0),
    )
  }

  const total = useMemo(
    () => cart.reduce((sum, item) => sum + item.price * item.quantity, 0),
    [cart],
  )

  const handleCheckout = (event) => {
    event.preventDefault()
    if (!cart.length) return

    alert(`Thanks ${formData.name || 'Gamer'}! Your order for ₹${total.toLocaleString('en-IN')} is confirmed.`)
    setCart([])
    setShowCheckout(false)
    setFormData({ name: '', email: '', address: '' })
  }

  return (
    <div className="min-h-screen bg-[#f3efe9] text-[#1f1a17]">
      <header className="sticky top-0 z-20 border-b border-[#d9c8b6] bg-[#f8f5f1]/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            
            <div className="leading-tight">
              <p className="text-[10px] uppercase tracking-[0.28em] text-[#7e5b45]">Tech</p>
              <h1 className="text-lg font-semibold tracking-[-0.04em] text-[#221b18]">Gadgets</h1>
            </div>
          </div>

          <nav className="hidden items-center gap-8 text-sm font-medium text-[#58463d] md:flex">
            <a href="#" className="transition hover:text-[#1f1a17]">Home</a>
            <a href="#products" className="transition hover:text-[#1f1a17]">Shop</a>
            <a href="#" className="transition hover:text-[#1f1a17]">Deals</a>
            <a href="#" className="transition hover:text-[#1f1a17]">Support</a>
          </nav>

          <button
            type="button"
            onClick={() => setShowCheckout(true)}
            className="inline-flex items-center gap-2 rounded-full border border-[#d0b29f] bg-[#f0e3d7] px-4 py-2 text-sm font-medium text-[#2f241f] transition hover:bg-[#e7d0b5]"
          >
            Cart
            <span className="rounded-full bg-[#3f2c24] px-2 py-0.5 text-xs font-bold text-[#f7f2ed]">
              {cart.reduce((count, item) => count + item.quantity, 0)}
            </span>
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="overflow-hidden rounded-[2rem] border border-[#ddd0c1] bg-white shadow-[0_20px_40px_rgba(71,53,44,0.06)]">
          <div className="grid gap-8 px-6 py-8 md:grid-cols-[1.15fr_0.85fr] md:px-10 md:py-10">
            <div className="flex flex-col justify-center">
              <span className="inline-flex w-fit rounded-full border border-[#d3b596] bg-[#f5eadb] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-[#704d38]">
                New Arrivals
              </span>
              <h2 className="mt-5 max-w-xl text-4xl font-bold tracking-[-0.04em] text-[#221b18] md:text-5xl">
                Smart tech for gaming, work, and everyday setup.
              </h2>
              <p className="mt-4 max-w-xl text-base leading-7 text-[#54453e] md:text-lg">
                Explore gaming consoles, desktop accessories, headphones, earbuds, and premium tech essentials built for productivity and play.
              </p>

              <div className="mt-7 flex flex-wrap items-center gap-4">
                <button
                  type="button"
                  onClick={() => setShowCheckout(true)}
                  className="rounded-full bg-[#3f2c24] px-6 py-3 text-sm font-semibold text-[#f7f2ed] transition hover:bg-[#2d201d]"
                >
                  Go to Checkout
                </button>
                <a
                  href="#products"
                  className="rounded-full border border-[#d1b69d] bg-[#f9f3ee] px-6 py-3 text-sm font-semibold text-[#2f241f] transition hover:bg-[#f1e4d7]"
                >
                  Explore Collection
                </a>
              </div>

              <div className="mt-8 grid max-w-lg grid-cols-3 gap-3">
                <div className="rounded-2xl border border-[#e7dccd] bg-[#faf5f0] p-3">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-[#7a6458]">Performance</p>
                  <p className="mt-2 text-lg font-semibold text-[#221b18]">4K / 120Hz</p>
                </div>
                <div className="rounded-2xl border border-[#e7dccd] bg-[#faf5f0] p-3">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-[#7a6458]">Storage</p>
                  <p className="mt-2 text-lg font-semibold text-[#221b18]">1 TB SSD</p>
                </div>
                <div className="rounded-2xl border border-[#e7dccd] bg-[#faf5f0] p-3">
                  <p className="text-[10px] uppercase tracking-[0.2em] text-[#7a6458]">Support</p>
                  <p className="mt-2 text-lg font-semibold text-[#221b18]">24/7</p>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-center">
              <div className="w-full max-w-md overflow-hidden rounded-[2rem] border border-[#d7c2a8] bg-[#f7efe7] p-3 shadow-[0_18px_35px_rgba(60,46,39,0.08)]">
                <img
                  src="https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=900&q=80"
                  alt="Featured gaming console"
                  className="h-[420px] w-full rounded-[1.5rem] object-cover"
                />
              </div>
            </div>
          </div>
        </section>

        <section id="products" className="mt-10">
          <div className="mb-6 flex items-end justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#7e5b45]">Featured collection</p>
              <h3 className="mt-2 text-3xl font-bold text-[#221b18]">Tech gadgets & gaming essentials</h3>
            </div>
            <span className="rounded-full border border-[#dfd0bd] bg-[#f8f3ee] px-3 py-1 text-sm text-[#5b463d]">
              10 essentials
            </span>
          </div>

          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
            {products.map((product) => (
              <article
                key={product.id}
                className="overflow-hidden rounded-[1.75rem] border border-[#e5d8c7] bg-[#fffdfb] shadow-[0_14px_28px_rgba(57,42,35,0.05)] transition duration-200 hover:-translate-y-1 hover:shadow-[0_18px_36px_rgba(57,42,35,0.08)]"
              >
                <div className={`${product.accent} p-2`}>
                  <img src={product.image} alt={product.name} className="h-52 w-full rounded-[1.2rem] object-cover" />
                </div>

                <div className="space-y-4 p-5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded-full bg-[#f3e7d8] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#6d4b39]">
                      {product.brand}
                    </span>
                    <span className="text-xs font-medium text-[#6f5a4f]">{product.badge}</span>
                  </div>

                  <div>
                    <h4 className="text-xl font-semibold text-[#221b18]">{product.name}</h4>
                    <p className="mt-2 text-sm leading-6 text-[#5b463d]">{product.description}</p>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-2xl font-bold text-[#3f2c24]">₹{product.price.toLocaleString('en-IN')}</span>
                    <button
                      type="button"
                      onClick={() => addToCart(product)}
                      className="rounded-full bg-[#3f2c24] px-4 py-2 text-sm font-semibold text-[#f7f2ed] transition hover:bg-[#2d201d]"
                    >
                      Add to cart
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="mt-10 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[2rem] border border-[#e3d8c9] bg-[#fffdfb] p-6">
            <div className="mb-5 flex items-center justify-between">
              <h3 className="text-2xl font-bold text-[#221b18]">Shopping cart</h3>
              <span className="text-sm text-[#68574d]">{cart.length} item(s)</span>
            </div>

            {cart.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-[#d9c8b6] bg-[#f7f1ea] px-6 py-10 text-center text-[#65564c]">
                Your cart is empty. Add a gadget to continue.
              </div>
            ) : (
              <div className="space-y-4">
                {cart.map((item) => (
                  <div key={item.id} className="flex items-center justify-between gap-3 rounded-2xl border border-[#eadfce] bg-[#f8f3ee] p-4">
                    <div>
                      <p className="font-semibold text-[#221b18]">{item.name}</p>
                      <p className="text-sm text-[#7a5d48]">₹{item.price.toLocaleString('en-IN')} each</p>
                    </div>

                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => updateQuantity(item.id, -1)}
                        className="flex h-8 w-8 items-center justify-center rounded-full bg-[#f0e0cf] text-lg text-[#2f241f] hover:bg-[#e6cfb4]"
                        aria-label={`Decrease quantity for ${item.name}`}
                      >
                        −
                      </button>
                      <span className="min-w-6 text-center font-semibold text-[#221b18]">{item.quantity}</span>
                      <button
                        type="button"
                        onClick={() => updateQuantity(item.id, 1)}
                        className="flex h-8 w-8 items-center justify-center rounded-full bg-[#f0e0cf] text-lg text-[#2f241f] hover:bg-[#e6cfb4]"
                        aria-label={`Increase quantity for ${item.name}`}
                      >
                        +
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <aside className="rounded-[2rem] border border-[#d9c8b6] bg-[#f5ebdf] p-6">
            <h3 className="text-2xl font-bold text-[#221b18]">Order summary</h3>

            <div className="mt-6 space-y-4 text-sm text-[#574a43]">
              <div className="flex justify-between">
                <span>Subtotal</span>
                <span>₹{total.toLocaleString('en-IN')}</span>
              </div>
              <div className="flex justify-between">
                <span>Shipping</span>
                <span>{total > 0 ? '₹399' : '₹0'}</span>
              </div>
              <div className="flex justify-between">
                <span>Tax</span>
                <span>{total > 0 ? '₹299' : '₹0'}</span>
              </div>
            </div>

            <div className="mt-6 border-t border-[#d4b89d] pt-4">
              <div className="flex items-center justify-between text-lg font-bold text-[#221b18]">
                <span>Total</span>
                <span>₹{total > 0 ? (total + 399 + 299).toLocaleString('en-IN') : 0}</span>
              </div>
            </div>

            <button
              type="button"
              disabled={!cart.length}
              onClick={() => setShowCheckout(true)}
              className="mt-6 w-full rounded-full bg-[#3f2c24] px-4 py-3 text-sm font-semibold text-[#f7f2ed] transition hover:bg-[#2d201d] disabled:cursor-not-allowed disabled:bg-[#d8c8b8] disabled:text-[#867660]"
            >
              Proceed to checkout
            </button>
          </aside>
        </section>

        {showCheckout && (
          <section className="mt-10 rounded-[2rem] border border-[#e3d8c9] bg-[#fffdfb] p-6 shadow-[0_24px_40px_rgba(69,58,49,0.05)]">
            <div className="mb-6">
              <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#7e5b45]">Checkout</p>
              <h3 className="mt-2 text-3xl font-bold text-[#221b18]">Complete your purchase</h3>
            </div>

            <form onSubmit={handleCheckout} className="grid gap-6 lg:grid-cols-[1fr_0.8fr]">
              <div className="space-y-4">
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-[#554a46]">Full name</span>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(event) => setFormData({ ...formData, name: event.target.value })}
                    required
                    className="w-full rounded-2xl border border-[#dbc8b0] bg-[#f7f1ea] px-4 py-3 text-[#221b18] outline-none placeholder:text-[#89766b] focus:border-[#8b6552]"
                    placeholder="John Doe"
                  />
                </label>

                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-[#554a46]">Email</span>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(event) => setFormData({ ...formData, email: event.target.value })}
                    required
                    className="w-full rounded-2xl border border-[#dbc8b0] bg-[#f7f1ea] px-4 py-3 text-[#221b18] outline-none placeholder:text-[#89766b] focus:border-[#8b6552]"
                    placeholder="john@example.com"
                  />
                </label>

                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-[#554a46]">Shipping address</span>
                  <textarea
                    value={formData.address}
                    onChange={(event) => setFormData({ ...formData, address: event.target.value })}
                    required
                    rows="4"
                    className="w-full rounded-2xl border border-[#dbc8b0] bg-[#f7f1ea] px-4 py-3 text-[#221b18] outline-none placeholder:text-[#89766b] focus:border-[#8b6552]"
                    placeholder="123 Game Street, New York, NY"
                  />
                </label>
              </div>

              <div className="rounded-2xl border border-[#dbc8b0] bg-[#f7f1ea] p-5">
                <h4 className="text-xl font-semibold text-[#221b18]">Payment</h4>
                <div className="mt-4 space-y-3 text-sm text-[#554a46]">
                  {cart.map((item) => (
                    <div key={item.id} className="flex items-center justify-between">
                      <span>
                        {item.name} x {item.quantity}
                      </span>
                      <span>₹{(item.price * item.quantity).toLocaleString('en-IN')}</span>
                    </div>
                  ))}
                </div>

                <div className="mt-5 space-y-3 border-t border-[#d6bda1] pt-4 text-sm text-[#554a46]">
                  <div className="flex justify-between">
                    <span>Subtotal</span>
                    <span>₹{total.toLocaleString('en-IN')}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Shipping</span>
                    <span>{total > 0 ? '₹399' : '₹0'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Tax</span>
                    <span>{total > 0 ? '₹299' : '₹0'}</span>
                  </div>
                </div>

                <div className="mt-5 flex items-center justify-between border-t border-[#d6bda1] pt-4 text-lg font-bold text-[#221b18]">
                  <span>Total</span>
                  <span>₹{total > 0 ? (total + 399 + 299).toLocaleString('en-IN') : 0}</span>
                </div>

                <button
                  type="submit"
                  disabled={!cart.length}
                  className="mt-6 w-full rounded-full bg-[#3f2c24] px-4 py-3 text-sm font-semibold text-[#f7f2ed] transition hover:bg-[#2d201d] disabled:cursor-not-allowed disabled:bg-[#d6c6b8] disabled:text-[#877664]"
                >
                  Confirm Order
                </button>
              </div>
            </form>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
